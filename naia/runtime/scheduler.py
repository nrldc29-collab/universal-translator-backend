"""Bounded async scheduler for runtime tasks."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from runtime.events import EventLog, EventType


T = TypeVar("T")


class RuntimeBudgets(BaseModel):
    max_runtime_seconds: float = 10.0
    max_tool_calls: int = 5
    max_concurrent_tasks: int = 3
    max_queue_size: int = 100


class SchedulerSnapshot(BaseModel):
    budgets: RuntimeBudgets
    queued_tasks: int = 0
    tool_calls_by_session: dict[str, int] = Field(default_factory=dict)


class SchedulerRejected(RuntimeError):
    pass


class Scheduler:
    def __init__(
        self,
        event_log: EventLog,
        budgets: RuntimeBudgets | None = None,
    ) -> None:
        self.event_log = event_log
        self.budgets = budgets or RuntimeBudgets()
        self._semaphore = asyncio.Semaphore(self.budgets.max_concurrent_tasks)
        self._queued_tasks = 0
        self._tool_calls_by_session: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    async def run(
        self,
        *,
        task_name: str,
        module: str,
        session_id: str | None,
        task_factory: Callable[[], Awaitable[T]],
        state_snapshot: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> T:
        async with self._lock:
            if self._queued_tasks >= self.budgets.max_queue_size:
                raise SchedulerRejected("scheduler queue budget exceeded")
            self._queued_tasks += 1

        started = time.perf_counter()
        try:
            async with self._semaphore:
                await self.event_log.emit(
                    EventType.SCHEDULER_TASK_STARTED,
                    module="runtime.scheduler",
                    session_id=session_id,
                    state_snapshot=state_snapshot,
                    details={"task_name": task_name, "task_module": module},
                )
                result = await asyncio.wait_for(
                    task_factory(),
                    timeout=timeout_seconds or self.budgets.max_runtime_seconds,
                )
                latency_ms = (time.perf_counter() - started) * 1000
                await self.event_log.emit(
                    EventType.SCHEDULER_TASK_COMPLETED,
                    module="runtime.scheduler",
                    session_id=session_id,
                    latency_ms=latency_ms,
                    state_snapshot=state_snapshot,
                    details={"task_name": task_name, "task_module": module},
                )
                return result
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            await self.event_log.emit(
                EventType.SCHEDULER_TASK_FAILED,
                module="runtime.scheduler",
                session_id=session_id,
                latency_ms=latency_ms,
                state_snapshot=state_snapshot,
                details={"task_name": task_name, "task_module": module},
                error=str(exc),
            )
            raise
        finally:
            async with self._lock:
                self._queued_tasks = max(0, self._queued_tasks - 1)

    async def record_tool_call(self, session_id: str) -> None:
        self._tool_calls_by_session[session_id] += 1
        if self._tool_calls_by_session[session_id] > self.budgets.max_tool_calls:
            raise SchedulerRejected("tool call budget exceeded")

    def snapshot(self) -> dict[str, Any]:
        return SchedulerSnapshot(
            budgets=self.budgets,
            queued_tasks=self._queued_tasks,
            tool_calls_by_session=dict(self._tool_calls_by_session),
        ).model_dump(mode="json")
