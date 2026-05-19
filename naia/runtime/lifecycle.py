"""Lifecycle management for cognitive runtime sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from runtime.events import EventLog, EventType
from runtime.state import CognitiveState


class LifecycleState(StrEnum):
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"
    TERMINATED = "TERMINATED"


class LifecycleTransition(BaseModel):
    session_id: str
    from_state: str
    to_state: str
    reason: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LifecycleManager:
    def __init__(self, event_log: EventLog) -> None:
        self.event_log = event_log
        self._transitions: list[LifecycleTransition] = []
        self._active_sessions: dict[str, str] = {}

    async def transition(
        self,
        state: CognitiveState,
        to_state: LifecycleState,
        *,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> LifecycleTransition:
        transition = LifecycleTransition(
            session_id=state.session_id,
            from_state=state.lifecycle_state,
            to_state=to_state.value,
            reason=reason,
        )
        state.lifecycle_state = to_state.value
        state.touch()
        self._transitions.append(transition)

        if to_state in {
            LifecycleState.COMPLETED,
            LifecycleState.FAILED,
            LifecycleState.TERMINATED,
        }:
            self._active_sessions.pop(state.session_id, None)
        else:
            self._active_sessions[state.session_id] = to_state.value

        await self.event_log.emit(
            EventType.LIFECYCLE_TRANSITIONED,
            module="runtime.lifecycle",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            details={
                "from_state": transition.from_state,
                "to_state": transition.to_state,
                "reason": reason,
                **(details or {}),
            },
        )
        return transition

    async def start(self, state: CognitiveState) -> None:
        await self.event_log.emit(
            EventType.SESSION_CREATED,
            module="runtime.lifecycle",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
        )
        await self.transition(state, LifecycleState.RUNNING, reason="session started")

    async def verify(self, state: CognitiveState) -> None:
        await self.transition(
            state, LifecycleState.VERIFYING, reason="response verification started"
        )

    async def complete(self, state: CognitiveState) -> None:
        await self.transition(
            state, LifecycleState.COMPLETED, reason="session completed"
        )
        await self.event_log.emit(
            EventType.SESSION_COMPLETED,
            module="runtime.lifecycle",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
        )

    async def fail(self, state: CognitiveState, error: str) -> None:
        state.record_error(error)
        await self.transition(
            state,
            LifecycleState.FAILED,
            reason="session failed",
            details={"error": error},
        )
        await self.event_log.emit(
            EventType.FAILURE_OCCURRED,
            module="runtime.lifecycle",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            error=error,
        )

    async def recover(self, state: CognitiveState, reason: str) -> None:
        await self.transition(
            state, LifecycleState.RECOVERING, reason=reason
        )
        await self.event_log.emit(
            EventType.RECOVERY_TRIGGERED,
            module="runtime.lifecycle",
            session_id=state.session_id,
            state_snapshot=state.snapshot(),
            details={"reason": reason},
        )

    def active_sessions(self) -> dict[str, str]:
        return dict(self._active_sessions)

    def transitions(self) -> list[dict[str, Any]]:
        return [
            transition.model_dump(mode="json") for transition in self._transitions
        ]
