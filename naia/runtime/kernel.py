"""Cognitive Runtime Kernel for NAIA with horizontal scaling support."""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any

from pydantic import BaseModel, Field

from agents.agent_runtime import AgentRuntime
from memory.memory_engine import MemoryEngine
from runtime.events import EventLog, EventType
from runtime.lifecycle import LifecycleManager
from runtime.pipeline import CognitivePipeline, PipelineOutput
from runtime.scheduler import RuntimeBudgets, Scheduler
from runtime.state import CognitiveState
from tools.executor import ToolExecutor
from tools.tool_router import ToolRouter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input limits
# ---------------------------------------------------------------------------

_MAX_INPUT_LENGTH = 8000
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize_input(text: str) -> str:
    """Strip control characters and enforce length limit on user input."""
    cleaned = _CONTROL_CHAR_RE.sub("", text).strip()
    if len(cleaned) > _MAX_INPUT_LENGTH:
        logger.info("kernel_input_truncated to=%d", _MAX_INPUT_LENGTH)
        cleaned = cleaned[:_MAX_INPUT_LENGTH]
    return cleaned


class KernelResponse(BaseModel):
    session_id: str
    state: str
    intent: str
    task_type: str
    complexity_level: str
    risk_level: str
    cognitive_mode: str
    reasoning_depth: int
    verification_level: str
    confidence: float
    response: str
    active_modules: list[str] = Field(default_factory=list)
    telemetry: dict[str, Any] = Field(default_factory=dict)
    route_plan: dict[str, Any] = Field(default_factory=dict)
    synthesis: dict[str, Any] = Field(default_factory=dict)


class CognitiveRuntimeKernel:
    """The stable orchestrator for NAIA runtime execution with horizontal scaling support."""

    # Class-level registry for kernel instances (enables multiple instances for scaling).
    _instances: dict[str, "CognitiveRuntimeKernel"] = {}
    _instances_lock = threading.Lock()

    def __init__(
        self,
        *,
        instance_id: str | None = None,
        event_log: EventLog | None = None,
        budgets: RuntimeBudgets | None = None,
        memory_engine: MemoryEngine | None = None,
        tool_executor: ToolExecutor | None = None,
        tool_router: ToolRouter | None = None,
        agent_runtime: AgentRuntime | None = None,
    ) -> None:
        self.instance_id = instance_id or f"kernel_{id(self)}"
        self.event_log = event_log or EventLog()
        self.scheduler = Scheduler(self.event_log, budgets=budgets)
        self.lifecycle = LifecycleManager(self.event_log)
        self.pipeline = CognitivePipeline(
            self.event_log,
            lifecycle=self.lifecycle,
            scheduler=self.scheduler,
            memory_engine=memory_engine,
            tool_executor=tool_executor,
            tool_router=tool_router,
            agent_runtime=agent_runtime,
        )
        self._process_count = 0
        self._process_errors = 0
        self._empty_input_count = 0
        self._total_latency_ms = 0.0

        with self._instances_lock:
            CognitiveRuntimeKernel._instances[self.instance_id] = self
        logger.info("Initialized kernel instance: %s", self.instance_id)

    @classmethod
    def get_instance(cls, instance_id: str = "default") -> "CognitiveRuntimeKernel | None":
        """Return a specific kernel instance by id, or ``None`` if not found."""
        return cls._instances.get(instance_id)

    @classmethod
    def list_instances(cls) -> list[str]:
        """List all registered kernel instances."""
        return list(cls._instances.keys())

    @classmethod
    def remove_instance(cls, instance_id: str) -> bool:
        """Remove a kernel instance from the registry."""
        if instance_id in cls._instances:
            del cls._instances[instance_id]
            logger.info("Removed kernel instance: %s", instance_id)
            return True
        return False

    async def process_user_input(
        self,
        user_input: str,
        *,
        source: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> KernelResponse:
        start_time = time.perf_counter()
        try:
            if not user_input or not user_input.strip():
                self._empty_input_count += 1
                logger.debug("Empty input rejected")
                return KernelResponse(
                    session_id="empty",
                    state="rejected",
                    intent="empty_input",
                    task_type="none",
                    complexity_level="trivial",
                    risk_level="none",
                    cognitive_mode="rejection",
                    reasoning_depth=0,
                    verification_level="none",
                    confidence=0.0,
                    response="Input is empty. Please provide a message.",
                    active_modules=[],
                    route_plan={},
                    synthesis={},
                    telemetry={"rejection_reason": "empty_input"},
                )

            user_input = _sanitize_input(user_input)
            started = time.perf_counter()
            state = self.create_session(user_input)
            await self.event_log.emit(
                EventType.INPUT_RECEIVED,
                module="runtime.kernel",
                session_id=state.session_id,
                state_snapshot=state.snapshot(),
                details={"source": source, "metadata": metadata or {}},
            )

            try:
                await self.lifecycle.start(state)
                pipeline_output = await self.pipeline.execute(state)
                await self.lifecycle.complete(state)
                response = self._to_kernel_response(state, pipeline_output, started)
                self._process_count += 1
                latency_ms = (time.perf_counter() - start_time) * 1000
                self._total_latency_ms += latency_ms
                logger.info(f"Kernel process completed: session={state.session_id}, latency={latency_ms:.2f}ms")
                return response
            except Exception as exc:  # noqa: BLE001
                self._process_errors += 1
                logger.error(f"Kernel process failed: {exc}", exc_info=True)
                await self.lifecycle.fail(state, str(exc))
                latency_ms = (time.perf_counter() - start_time) * 1000
                return KernelResponse(
                    session_id=state.session_id,
                    state=state.lifecycle_state,
                    intent=state.intent,
                    task_type=state.task_type,
                    complexity_level=state.complexity_level,
                    risk_level=state.risk_level,
                    cognitive_mode="failure_containment",
                    reasoning_depth=state.reasoning_depth,
                    verification_level=state.verification_level,
                    confidence=0.0,
                    response="I hit an internal failure and stopped safely.",
                    active_modules=list(state.active_modules),
                    route_plan=dict(state.route_plan),
                    synthesis=dict(state.synthesis),
                    telemetry={
                        "latency_ms": latency_ms,
                        "errors": list(state.errors),
                        "fault": str(exc),
                    },
                )
        except Exception as e:
            self._process_errors += 1
            logger.error(f"Kernel process_user_input failed: {e}", exc_info=True)
            latency_ms = (time.perf_counter() - start_time) * 1000
            return KernelResponse(
                session_id="error",
                state="error",
                intent="error",
                task_type="error",
                complexity_level="unknown",
                risk_level="unknown",
                cognitive_mode="error",
                reasoning_depth=0,
                verification_level="none",
                confidence=0.0,
                response="An internal error occurred.",
                active_modules=[],
                route_plan={},
                synthesis={},
                telemetry={"latency_ms": latency_ms, "error": str(e)},
            )

    def create_session(self, user_input: str) -> CognitiveState:
        try:
            return CognitiveState(user_input=user_input)
        except Exception as e:
            logger.error(f"Failed to create session: {e}", exc_info=True)
            raise

    async def telemetry_snapshot(self, *, limit: int = 100) -> dict[str, Any]:
        try:
            events = await self.event_log.snapshot(limit=limit)
            return {
                "instance_id": self.instance_id,
                "events": events,
                "scheduler": self.scheduler.snapshot(),
                "active_sessions": self.lifecycle.active_sessions(),
                "lifecycle_transitions": self.lifecycle.transitions()[-limit:],
                "process_count": self._process_count,
                "process_errors": self._process_errors,
                "empty_input_count": self._empty_input_count,
                "error_rate": self._process_errors / self._process_count if self._process_count > 0 else 0,
                "avg_latency_ms": self._total_latency_ms / self._process_count if self._process_count > 0 else 0,
            }
        except Exception as e:
            logger.error(f"Failed to get telemetry snapshot: {e}", exc_info=True)
            return {
                "instance_id": self.instance_id,
                "error": str(e),
                "process_count": self._process_count,
                "process_errors": self._process_errors,
            }

    def get_statistics(self) -> dict[str, Any]:
        """Get kernel statistics."""
        return {
            "instance_id": self.instance_id,
            "process_count": self._process_count,
            "process_errors": self._process_errors,
            "empty_input_count": self._empty_input_count,
            "error_rate": self._process_errors / self._process_count if self._process_count > 0 else 0,
            "avg_latency_ms": self._total_latency_ms / self._process_count if self._process_count > 0 else 0,
            "total_instances": len(self._instances),
            "active_sessions": len(self.lifecycle.active_sessions()),
        }

    def _to_kernel_response(
        self,
        state: CognitiveState,
        pipeline_output: PipelineOutput,
        started: float,
    ) -> KernelResponse:
        telemetry = dict(pipeline_output.telemetry)
        telemetry.setdefault("latency_ms", (time.perf_counter() - started) * 1000)
        return KernelResponse(
            session_id=state.session_id,
            state=state.lifecycle_state,
            intent=pipeline_output.intent,
            task_type=state.task_type,
            complexity_level=state.complexity_level,
            risk_level=pipeline_output.risk_level,
            cognitive_mode=pipeline_output.cognitive_mode,
            reasoning_depth=state.reasoning_depth,
            verification_level=state.verification_level,
            confidence=pipeline_output.confidence,
            response=pipeline_output.message,
            active_modules=pipeline_output.active_modules,
            telemetry=telemetry,
            route_plan=pipeline_output.route_plan,
            synthesis=pipeline_output.synthesis,
        )
