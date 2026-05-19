"""Controlled cognitive pipeline for the NAIA runtime kernel."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from agents.agent_core import AgentState
from agents.agent_runtime import AgentRuntime
from cognition.router.router import CognitiveRouter, RoutePlan
from governance.approval_queue import ApprovalQueue
from governance.decision_log import DecisionLog
from governance.governance_hook import governance_hook
from memory.episodic import EpisodicMemory
from memory.memory_engine import MemoryEngine
from runtime.events import EventLog, EventType
from runtime.lifecycle import LifecycleManager
from runtime.scheduler import Scheduler
from runtime.state import CognitiveState
from synthesis.final_renderer import FinalRenderer, SynthesisContext
from synthesis.response_merger import SourceOutput, SourceType
from tools.executor import ToolExecutor
from tools.registry import ToolRequest, ToolStatus
from tools.tool_router import ToolRouter


class PipelineOutput(BaseModel):
    session_id: str
    message: str
    intent: str
    cognitive_mode: str
    risk_level: str
    confidence: float
    active_modules: list[str] = Field(default_factory=list)
    telemetry: dict[str, Any] = Field(default_factory=dict)
    route_plan: dict[str, Any] = Field(default_factory=dict)
    synthesis: dict[str, Any] = Field(default_factory=dict)


class CognitivePipeline:
    """A predictable pipeline that orchestrates, but does not think deeply."""

    def __init__(
        self,
        event_log: EventLog,
        lifecycle: LifecycleManager,
        scheduler: Scheduler,
        router: CognitiveRouter | None = None,
        final_renderer: FinalRenderer | None = None,
        memory_engine: MemoryEngine | None = None,
        tool_executor: ToolExecutor | None = None,
        tool_router: ToolRouter | None = None,
        agent_runtime: AgentRuntime | None = None,
        decision_log: DecisionLog | None = None,
        approval_queue: ApprovalQueue | None = None,
    ) -> None:
        self.event_log = event_log
        self.lifecycle = lifecycle
        self.scheduler = scheduler
        self.router = router or CognitiveRouter()
        self.final_renderer = final_renderer or FinalRenderer()
        self.memory_engine = memory_engine or MemoryEngine()
        self.tool_executor = tool_executor or ToolExecutor()
        self.tool_router = tool_router or ToolRouter()
        self.agent_runtime = agent_runtime or AgentRuntime(
            memory_engine=self.memory_engine,
            tool_executor=self.tool_executor,
        )
        self.decision_log = decision_log or DecisionLog()
        self.approval_queue = approval_queue or ApprovalQueue()

    async def execute(self, state: CognitiveState) -> PipelineOutput:
        started = time.perf_counter()

        await self._input_stage(state)
        await self._routing_stage(state)
        await self._intent_detection_stage(state)
        await self._risk_precheck_stage(state)
        await self._memory_retrieval_stage(state)
        await self._tool_execution_stage(state)
        await self._agent_execution_stage(state)
        dispatch = await self.scheduler.run(
            task_name="cognitive_dispatch",
            module="runtime.pipeline",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            task_factory=lambda: self._cognitive_dispatch_stage(state),
            timeout_seconds=state.execution_budget.get("max_time_seconds"),
        )
        await self.lifecycle.verify(state)
        output = await self._response_synthesis_stage(state, dispatch)
        await self._memory_write_stage(state, output)
        await self._telemetry_logging_stage(state, started)
        return output.model_copy(
            update={
                "active_modules": list(state.active_modules),
                "telemetry": dict(state.telemetry),
                "route_plan": dict(state.route_plan),
                "synthesis": dict(state.synthesis),
            }
        )

    async def _input_stage(self, state: CognitiveState) -> None:
        state.add_module("input_stage")
        state.normalized_input = " ".join(state.user_input.strip().split())
        state.touch()
        await self.event_log.emit(
            EventType.INPUT_NORMALIZED,
            module="runtime.pipeline.input",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            details={
                "input_length": len(state.user_input),
                "normalized_length": len(state.normalized_input),
            },
        )

    async def _routing_stage(self, state: CognitiveState) -> None:
        state.add_module("cognitive_routing_stage")
        route_plan = self.router.route(state.normalized_input)
        self._apply_route_plan(state, route_plan)
        await self.event_log.emit(
            EventType.ROUTE_SELECTED,
            module="cognition.router",
            session_id=state.session_id,
            latency_ms=route_plan.latency_ms,
            state_snapshot=state.snapshot(),
            details={
                "mode": route_plan.mode.value,
                "task_type": route_plan.task_type,
                "complexity": route_plan.complexity.complexity.value,
                "risk": route_plan.risk.risk.value,
                "reasoning_depth": route_plan.reasoning_depth,
                "reflection_enabled": route_plan.reflection_enabled,
                "memory_enabled": route_plan.memory_enabled,
                "tool_access": route_plan.tool_access,
                "verification_level": route_plan.verification_level.value,
                "agent_activation": route_plan.agent_activation,
                "execution_budget": route_plan.execution_budget.model_dump(mode="json"),
                "policy_triggers": route_plan.policy_triggers,
                "risk_triggers": route_plan.risk.reasons,
                "estimated_cost": route_plan.estimated_cost,
            },
        )

    async def _intent_detection_stage(self, state: CognitiveState) -> None:
        state.add_module("intent_detection_stage")
        state.touch()
        await self.event_log.emit(
            EventType.INTENT_CLASSIFIED,
            module="runtime.pipeline.intent",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            details={
                "intent": state.intent,
                "task_type": state.task_type,
                "confidence": state.confidence,
            },
        )

    async def _risk_precheck_stage(self, state: CognitiveState) -> None:
        state.add_module("risk_precheck_stage")
        state.touch()

        if state.risk_level in {"HIGH", "CRITICAL"}:
            allowed, reason = governance_hook(
                state, self.decision_log, self.approval_queue
            )
            if not allowed:
                state.route_plan["governance_blocked"] = True
                state.route_plan["governance_reason"] = reason
                state.cognitive_mode = "HIGH_RISK"
                await self.event_log.emit(
                    EventType.RISK_DETECTED,
                    module="runtime.pipeline.risk",
                    session_id=state.session_id,
                    state_snapshot=state.snapshot(),
                    details={
                        "risk_level": state.risk_level,
                        "governance_blocked": True,
                        "governance_reason": reason,
                        "requires_confirmation": state.route_plan.get("risk", {}).get(
                            "requires_confirmation", False
                        ),
                        "restricted_tools": state.route_plan.get("risk", {}).get(
                            "restricted_tools", []
                        ),
                        "reasons": state.route_plan.get("risk", {}).get("reasons", []),
                    },
                )
                return

        event_type = (
            EventType.RISK_DETECTED
            if state.risk_level in {"MEDIUM", "HIGH", "CRITICAL"}
            else EventType.RISK_PRECHECKED
        )
        await self.event_log.emit(
            event_type,
            module="runtime.pipeline.risk",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            details={
                "risk_level": state.risk_level,
                "governance_reviewed": state.risk_level in {"HIGH", "CRITICAL"},
                "requires_confirmation": state.route_plan.get("risk", {}).get(
                    "requires_confirmation", False
                ),
                "restricted_tools": state.route_plan.get("risk", {}).get(
                    "restricted_tools", []
                ),
                "reasons": state.route_plan.get("risk", {}).get("reasons", []),
            },
        )

    async def _memory_retrieval_stage(self, state: CognitiveState) -> None:
        state.add_module("memory_retrieval_stage")
        if not state.memory_enabled:
            state.touch()
            await self.event_log.emit(
                EventType.MEMORY_RETRIEVED,
                module="memory.memory_engine",
                session_id=state.session_id,
                state_snapshot=state.snapshot(),
                details={"enabled": False, "selected_count": 0},
            )
            return

        retrieval = self.memory_engine.retrieve(
            state.normalized_input,
            min_confidence=0.35,
            limit=5,
        )
        state.memory_context = retrieval.injected_context
        state.retrieved_memories = [
            {
                "memory_id": result.record.memory_id,
                "memory_type": result.record.memory_type.value,
                "content": result.record.content,
                "confidence": result.record.confidence,
                "importance": result.record.importance,
                "score": result.score,
                "similarity": result.similarity,
                "topic": result.record.topic,
            }
            for result in retrieval.memories
        ]
        state.touch()
        await self.event_log.emit(
            EventType.MEMORY_RETRIEVED,
            module="memory.memory_engine",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            details={
                "enabled": True,
                "selected_count": len(state.retrieved_memories),
                "candidate_count": retrieval.metadata.get("candidate_count", 0),
            },
        )

    async def _tool_execution_stage(self, state: CognitiveState) -> None:
        state.add_module("tool_execution_stage")
        if not state.tool_access:
            state.touch()
            await self.event_log.emit(
                EventType.TOOL_EXECUTED,
                module="tools.executor",
                session_id=state.session_id,
                state_snapshot=state.snapshot(),
                details={"enabled": False, "reason": "route disabled tool access"},
            )
            return

        route = self.tool_router.route(
            state.normalized_input,
            session_id=state.session_id,
        )
        if route.request is None:
            state.touch()
            await self.event_log.emit(
                EventType.TOOL_EXECUTED,
                module="tools.executor",
                session_id=state.session_id,
                state_snapshot=state.snapshot(),
                details={"enabled": True, "selected": False, "reason": route.reason},
            )
            return

        state.tool_requests.append(route.request.model_dump(mode="json"))
        max_tool_calls = int(state.execution_budget.get("max_tool_calls", 0))
        if max_tool_calls <= len(state.tool_results):
            blocked = {
                "tool_name": route.request.tool_name,
                "status": "blocked",
                "result": {},
                "logs": ["execution budget does not allow another tool call"],
                "risk_notes": ["tool budget exhausted"],
                "execution_time": 0.0,
                "metadata": {"route_reason": route.reason},
            }
            state.tool_results.append(blocked)
            state.touch()
            await self.event_log.emit(
                EventType.TOOL_EXECUTED,
                module="tools.executor",
                session_id=state.session_id,
                state_snapshot=state.snapshot(),
                details=blocked,
            )
            return

        await self.scheduler.record_tool_call(state.session_id)
        result = await self.scheduler.run(
            task_name=f"tool:{route.request.tool_name}",
            module="tools.executor",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            timeout_seconds=min(
                5.0,
                float(state.execution_budget.get("max_time_seconds", 5.0)),
            ),
            task_factory=lambda: self._execute_tool_request(state, route.request),
        )
        serialized = result.model_dump(mode="json")
        serialized["metadata"]["route_reason"] = route.reason
        state.tool_results.append(serialized)
        state.touch()
        await self.event_log.emit(
            EventType.TOOL_EXECUTED,
            module="tools.executor",
            session_id=state.session_id,
            latency_ms=result.execution_time * 1000,
            state_snapshot=state.snapshot(),
            details=serialized,
        )

    async def _agent_execution_stage(self, state: CognitiveState) -> None:
        state.add_module("agent_execution_stage")
        goal = self.agent_runtime.extract_goal(state.normalized_input)
        if goal is None:
            state.touch()
            return

        state.agent_requests.append({"goal": goal, "source": "chat"})
        agent = self.agent_runtime.create_agent(
            goal,
            session_id=state.session_id,
            metadata={
                "source": "runtime_pipeline",
                "risk_level": state.risk_level,
                "cognitive_mode": state.cognitive_mode,
            },
            auto_plan=True,
        )
        await self.event_log.emit(
            EventType.AGENT_CREATED,
            module="agents.agent_runtime",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            details=self.agent_runtime.summarize_agent(agent),
        )
        await self.event_log.emit(
            EventType.AGENT_PLANNED,
            module="agents.agent_runtime",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            details={
                "agent_id": agent.agent_id,
                "task_count": len(agent.tasks),
                "state": agent.state.value,
            },
        )

        agent = self.agent_runtime.run_agent(agent.agent_id, max_steps=6)
        summary = self.agent_runtime.summarize_agent(agent)
        state.agent_results.append(summary)
        state.touch()

        event = EventType.AGENT_COMPLETED
        if agent.state == AgentState.FAILED:
            event = EventType.AGENT_FAILED
        await self.event_log.emit(
            event,
            module="agents.agent_runtime",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            details=summary,
        )
        for task in agent.tasks:
            if task.result:
                await self.event_log.emit(
                    EventType.AGENT_TASK_COMPLETED,
                    module="agents.executor",
                    session_id=state.session_id,
                    state_snapshot=state.snapshot(),
                    details={
                        "agent_id": agent.agent_id,
                        "task_id": task.task_id,
                        "title": task.title,
                        "status": task.status.value,
                        "result": task.result,
                    },
                )

    async def _cognitive_dispatch_stage(self, state: CognitiveState) -> dict[str, Any]:
        state.add_module("cognitive_dispatch_stage")
        if state.cognitive_mode == "HIGH_RISK":
            dispatch = {
                "status": "blocked_pending_approval",
                "module": "cognition.router",
                "summary": "Execution requires explicit human approval.",
                "route_mode": state.cognitive_mode,
            }
        elif state.tool_results:
            latest_tool = state.tool_results[-1]
            dispatch = {
                "status": latest_tool.get("status", "failed"),
                "module": "tool_dispatch",
                "summary": self._tool_summary(latest_tool),
                "route_mode": state.cognitive_mode,
                "tool_result": latest_tool,
            }
        elif state.agent_results:
            latest_agent = state.agent_results[-1]
            dispatch = {
                "status": latest_agent.get("state", "FAILED").lower(),
                "module": "agent_dispatch",
                "summary": self._agent_summary(latest_agent),
                "route_mode": state.cognitive_mode,
                "agent_result": latest_agent,
            }
        else:
            dispatch = {
                "status": "accepted",
                "module": "cognition.router",
                "summary": "No specialized cognition module is attached yet.",
                "route_mode": state.cognitive_mode,
            }
        await self.event_log.emit(
            EventType.COGNITIVE_DISPATCHED,
            module="runtime.pipeline.dispatch",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            details=dispatch,
        )
        return dispatch

    async def _response_synthesis_stage(
        self, state: CognitiveState, dispatch: dict[str, Any]
    ) -> PipelineOutput:
        state.add_module("response_synthesis_stage")
        synthesis_result = self.final_renderer.render(
            self._source_outputs_for_state(state, dispatch),
            SynthesisContext(
                session_id=state.session_id,
                user_input=state.normalized_input,
                task_type=state.task_type,
                cognitive_mode=state.cognitive_mode,
                complexity_level=state.complexity_level,
                risk_level=state.risk_level,
                confidence=state.confidence,
            ),
        )
        state.synthesis = synthesis_result.model_dump(mode="json")
        state.confidence = synthesis_result.confidence

        state.touch()
        output = PipelineOutput(
            session_id=state.session_id,
            message=synthesis_result.response,
            intent=state.intent,
            cognitive_mode=state.cognitive_mode,
            risk_level=state.risk_level,
            confidence=state.confidence,
            active_modules=list(state.active_modules),
            telemetry=state.telemetry,
            route_plan=state.route_plan,
            synthesis=state.synthesis,
        )
        await self.event_log.emit(
            EventType.FINAL_RESPONSE_RENDERED,
            module="synthesis.final_renderer",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            details={
                "coherence_score": synthesis_result.coherence_score,
                "coherence_issues": synthesis_result.coherence_issues,
                "contradiction_count": synthesis_result.contradiction_count,
                "tone_mode": synthesis_result.tone_mode,
                "source_count": synthesis_result.source_count,
                "rewritten": synthesis_result.rewritten,
            },
        )
        await self.event_log.emit(
            EventType.RESPONSE_SYNTHESIZED,
            module="runtime.pipeline.synthesis",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            details={
                "confidence": output.confidence,
                "coherence_score": synthesis_result.coherence_score,
            },
        )
        return output

    async def _execute_tool_request(
        self, state: CognitiveState, request: ToolRequest
    ):
        context = self.tool_router.permission_context_for_route(
            tool_access=state.tool_access,
            risk_level=state.risk_level,
            session_id=state.session_id,
            confirmed=request.confirmed,
        )
        return self.tool_executor.execute(request, context)

    async def _memory_write_stage(
        self, state: CognitiveState, output: PipelineOutput
    ) -> None:
        state.add_module("memory_write_stage")
        writes: list[dict[str, Any]] = []

        semantic_candidate = self.memory_engine.extract_semantic_candidate(
            state.normalized_input,
            session_id=state.session_id,
        )
        if semantic_candidate is not None:
            semantic_result = self.memory_engine.write(semantic_candidate)
            writes.append(semantic_result.model_dump(mode="json"))
            await self.event_log.emit(
                EventType.MEMORY_VALIDATED,
                module="memory.memory_engine",
                session_id=state.session_id,
                state_snapshot=state.snapshot(),
                details=semantic_result.model_dump(mode="json"),
            )

        episodic_result = self.memory_engine.write_episodic(
            EpisodicMemory(
                session_id=state.session_id,
                event=f"{state.task_type} interaction completed",
                context=(
                    f"User: {state.normalized_input}\n"
                    f"Response: {output.message}\n"
                    f"Mode: {state.cognitive_mode}; risk: {state.risk_level}"
                ),
                importance=self._episodic_importance(state),
                confidence=max(0.5, output.confidence),
                metadata={
                    "task_type": state.task_type,
                    "cognitive_mode": state.cognitive_mode,
                    "risk_level": state.risk_level,
                    "complexity_level": state.complexity_level,
                    "retrieved_memory_count": len(state.retrieved_memories),
                },
            )
        )
        writes.append(episodic_result.model_dump(mode="json"))

        state.memory_writes = writes
        state.touch()
        await self.event_log.emit(
            EventType.MEMORY_WRITTEN,
            module="memory.memory_engine",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            details={
                "write_count": len(writes),
                "stored_count": sum(1 for write in writes if write.get("stored")),
                "statuses": [write.get("status") for write in writes],
            },
        )

    async def _telemetry_logging_stage(
        self, state: CognitiveState, started: float
    ) -> None:
        latency_ms = (time.perf_counter() - started) * 1000
        state.add_module("telemetry_logging_stage")
        state.telemetry.update(
            {
                "latency_ms": latency_ms,
                "pipeline_decisions": {
                    "intent": state.intent,
                    "task_type": state.task_type,
                    "complexity_level": state.complexity_level,
                    "risk_level": state.risk_level,
                    "cognitive_mode": state.cognitive_mode,
                    "reasoning_depth": state.reasoning_depth,
                    "verification_level": state.verification_level,
                },
                "routing": state.route_plan,
                "synthesis": state.synthesis,
                "memory": {
                    "retrieved_count": len(state.retrieved_memories),
                    "write_count": len(state.memory_writes),
                    "retrieved": state.retrieved_memories,
                    "writes": state.memory_writes,
                },
                "tools": {
                    "request_count": len(state.tool_requests),
                    "result_count": len(state.tool_results),
                    "requests": state.tool_requests,
                    "results": state.tool_results,
                },
                "agents": {
                    "request_count": len(state.agent_requests),
                    "result_count": len(state.agent_results),
                    "requests": state.agent_requests,
                    "results": state.agent_results,
                },
                "module_usage": list(state.active_modules),
                "errors": list(state.errors),
            }
        )
        state.touch()
        await self.event_log.emit(
            EventType.TELEMETRY_RECORDED,
            module="runtime.pipeline.telemetry",
            session_id=state.session_id,
            latency_ms=latency_ms,
            state_snapshot=state.snapshot(),
            details=state.telemetry,
        )

    def _apply_route_plan(
        self, state: CognitiveState, route_plan: RoutePlan
    ) -> None:
        serialized = route_plan.model_dump(mode="json")
        state.route_plan = serialized
        state.intent = route_plan.intent
        state.task_type = route_plan.task_type
        state.cognitive_mode = route_plan.mode.value
        state.complexity_level = route_plan.complexity.complexity.value
        state.risk_level = route_plan.risk.risk.value
        state.reasoning_depth = route_plan.reasoning_depth
        state.reflection_enabled = route_plan.reflection_enabled
        state.memory_enabled = route_plan.memory_enabled
        state.tool_access = route_plan.tool_access
        state.verification_level = route_plan.verification_level.value
        state.agent_activation = route_plan.agent_activation
        state.response_priority = route_plan.response_priority.value
        state.execution_budget = route_plan.execution_budget.model_dump(mode="json")
        state.confidence = route_plan.classification.confidence
        state.touch()

    def _source_outputs_for_state(
        self, state: CognitiveState, dispatch: dict[str, Any]
    ) -> list[SourceOutput]:
        if state.cognitive_mode == "HIGH_RISK":
            return [
                SourceOutput(
                    source=SourceType.GOVERNANCE,
                    claims=[
                        "I cannot carry out that action without explicit human approval."
                    ],
                    risks=state.route_plan.get("risk", {}).get("reasons", []),
                    confidence=0.92,
                    verified=True,
                ),
                SourceOutput(
                    source=SourceType.REASONING,
                    claims=[
                        "I can help make the request safer before any action is taken."
                    ],
                    supporting_points=[
                        "Clarify the exact scope.",
                        "Confirm what can be reversed.",
                        "Review the intended outcome before execution.",
                    ],
                    confidence=0.78,
                ),
            ]

        tool_outputs = self._tool_source_outputs(state)
        agent_outputs = self._agent_source_outputs(state)

        if state.task_type == "conversation" and len(state.normalized_input.split()) <= 3:
            outputs = [
                SourceOutput(
                    source=SourceType.REASONING,
                    claims=["Hi. I am here."],
                    confidence=0.9,
                )
            ]
            outputs.extend(tool_outputs)
            outputs.extend(agent_outputs)
            return self._with_memory_source(state, outputs)

        task_claims = {
            "coding": "I can help work through this in a controlled and reviewable way.",
            "research": "I can help research this with evidence and clear uncertainty.",
            "planning": "I can help plan this in a structured and reviewable way.",
            "creative": "I can help shape this into a coherent draft.",
            "reasoning": "I can help reason through this clearly.",
            "automation": "I can help design the automation in a controlled and reviewable way.",
            "math": "I can help solve this carefully.",
            "analysis": "I can help analyze this clearly and step by step.",
            "conversation": "I can help with that.",
        }
        supporting_points = [
            "I will keep the response focused on the request.",
            "I will call out uncertainty when it matters.",
        ]
        if state.verification_level in {"HIGH", "STRICT"}:
            supporting_points.append(
                "I will treat safety and verification as primary constraints."
            )

        outputs = []
        outputs.extend(agent_outputs)
        outputs.extend(tool_outputs)
        outputs.extend([
            SourceOutput(
                source=SourceType.REASONING,
                claims=[task_claims.get(state.task_type, "I can help with that.")],
                supporting_points=supporting_points,
                confidence=max(0.55, state.confidence),
            ),
            SourceOutput(
                source=SourceType.DISPATCH,
                claims=[dispatch.get("summary", "")],
                confidence=0.52,
                metadata={"status": dispatch.get("status")},
            ),
        ])
        return self._with_memory_source(state, outputs)

    def _with_memory_source(
        self, state: CognitiveState, outputs: list[SourceOutput]
    ) -> list[SourceOutput]:
        if not state.retrieved_memories:
            return outputs

        top_memories = state.retrieved_memories[:3]
        for memory in top_memories:
            if not memory.get("content"):
                continue
            confidence = min(
                1.0,
                max(
                    float(memory.get("confidence", 0.0)),
                    float(memory.get("score", 0.0)),
                ),
            )
            outputs.append(
                SourceOutput(
                    source=SourceType.MEMORY,
                    claims=[f"Relevant context: {memory['content']}"],
                    confidence=confidence,
                    metadata={
                        "retrieved_count": len(state.retrieved_memories),
                        "memory_id": memory["memory_id"],
                        "retrieval_score": memory.get("score", 0.0),
                    },
                )
            )
        return outputs

    def _episodic_importance(self, state: CognitiveState) -> float:
        importance = 0.45
        if state.complexity_level in {"HIGH", "EXTREME"}:
            importance += 0.2
        if state.risk_level in {"HIGH", "CRITICAL"}:
            importance += 0.2
        if state.retrieved_memories:
            importance += 0.1
        if state.tool_results:
            importance += 0.1
        if state.agent_results:
            importance += 0.15
        return min(1.0, importance)

    def _agent_source_outputs(self, state: CognitiveState) -> list[SourceOutput]:
        outputs: list[SourceOutput] = []
        for result in state.agent_results:
            confidence = (
                0.85 if result.get("state") == AgentState.COMPLETED.value else 0.55
            )
            outputs.append(
                SourceOutput(
                    source=SourceType.AGENT,
                    claims=[self._agent_summary(result)],
                    confidence=confidence,
                    verified=result.get("state") == AgentState.COMPLETED.value,
                    metadata={"agent_id": result.get("agent_id")},
                )
            )
        return outputs

    def _agent_summary(self, result: dict[str, Any]) -> str:
        goal = result.get("goal", "goal")
        state_val = result.get("state", "UNKNOWN")
        tasks = result.get("tasks", [])
        completed = [task for task in tasks if task.get("status") == "COMPLETED"]
        last_result = next(
            (
                task.get("result")
                for task in reversed(tasks)
                if task.get("result")
                and "verify" not in str(task.get("title", "")).lower()
            ),
            None,
        )
        if state_val == AgentState.COMPLETED.value:
            if last_result:
                return f"Agent completed the goal '{goal}'. {last_result}"
            return f"Agent completed the goal '{goal}'."
        if state_val == AgentState.FAILED.value:
            return (
                f"Agent could not complete the goal '{goal}': "
                f"{result.get('last_error')}"
            )
        return (
            f"Agent is {state_val.lower()} on '{goal}' with "
            f"{len(completed)}/{len(tasks)} tasks complete."
        )

    def _tool_source_outputs(self, state: CognitiveState) -> list[SourceOutput]:
        outputs: list[SourceOutput] = []
        for result in state.tool_results:
            outputs.append(
                SourceOutput(
                    source=SourceType.TOOL,
                    claims=[self._tool_summary(result)],
                    confidence=(
                        0.9 if result.get("status") == ToolStatus.SUCCESS.value else 0.65
                    ),
                    verified=result.get("status") == ToolStatus.SUCCESS.value,
                    metadata={"tool_name": result.get("tool_name")},
                    risks=result.get("risk_notes", []),
                )
            )
        return outputs

    def _tool_summary(self, result: dict[str, Any]) -> str:
        status = result.get("status", "failed")
        tool_name = result.get("tool_name", "tool")
        payload = result.get("result", {})
        logs = result.get("logs", [])
        if status == "blocked":
            reason = logs[0] if logs else "blocked by governance"
            return f"Action blocked: {reason}."
        if status == "failed":
            reason = logs[0] if logs else "execution failed"
            return f"Action failed: {reason}."
        if tool_name == "run_python":
            stdout = str(payload.get("stdout", "")).strip()
            stderr = str(payload.get("stderr", "")).strip()
            if stdout:
                return f"Result: {stdout[:1000]}"
            if stderr:
                return f"Result: Python reported an error: {stderr[:1000]}"
            return f"Result: Python exited with code {payload.get('returncode')}."
        if tool_name == "read_file":
            content = str(payload.get("content", ""))
            path = payload.get("path", "")
            return f"Result: read {path}. {content[:1000]}"
        if tool_name == "list_directory":
            entries = payload.get("entries", [])
            names = ", ".join(entry.get("name", "") for entry in entries[:20])
            return f"Result: {names}"
        if tool_name == "write_file":
            return f"Result: wrote {payload.get('path')}."
        if tool_name in {"fetch_url", "api_get"}:
            content = str(payload.get("content", ""))
            return f"Result: {content[:1000]}"
        if tool_name == "web_search":
            results = payload.get("results", [])
            titles = ", ".join(item.get("title", "") for item in results[:5])
            return f"Result: {titles}" if titles else "Result: no search results found."
        return f"Result: {payload}"
