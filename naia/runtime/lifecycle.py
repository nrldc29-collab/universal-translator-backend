"""Lifecycle management for cognitive runtime sessions."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from runtime.events import EventLog, EventType
from runtime.state import CognitiveState

logger = logging.getLogger(__name__)


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
        self._lock = threading.Lock()
        self._transition_count = 0
        self._session_count = 0
        self._failure_count = 0
        logger.info("LifecycleManager initialized")

    async def transition(
        self,
        state: CognitiveState,
        to_state: LifecycleState,
        *,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> LifecycleTransition:
        try:
            with self._lock:
                transition = LifecycleTransition(
                    session_id=state.session_id,
                    from_state=state.lifecycle_state,
                    to_state=to_state.value,
                    reason=reason,
                )
                state.lifecycle_state = to_state.value
                state.touch()
                self._transitions.append(transition)
                self._transition_count += 1

                if to_state in {
                    LifecycleState.COMPLETED,
                    LifecycleState.FAILED,
                    LifecycleState.TERMINATED,
                }:
                    self._active_sessions.pop(state.session_id, None)
                else:
                    self._active_sessions[state.session_id] = to_state.value

            logger.debug(f"Lifecycle transition: {state.session_id} {transition.from_state} -> {to_state.value}")
            
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
        except Exception as e:
            logger.error(f"Lifecycle transition failed: {e}", exc_info=True)
            raise

    async def start(self, state: CognitiveState) -> None:
        try:
            with self._lock:
                self._session_count += 1
            await self.event_log.emit(
                EventType.SESSION_CREATED,
                module="runtime.lifecycle",
                session_id=state.session_id,
                state_snapshot=state.snapshot(),
            )
            await self.transition(state, LifecycleState.RUNNING, reason="session started")
            logger.info(f"Session started: {state.session_id}")
        except Exception as e:
            logger.error(f"Failed to start session {state.session_id}: {e}", exc_info=True)
            raise

    async def verify(self, state: CognitiveState) -> None:
        try:
            await self.transition(
                state, LifecycleState.VERIFYING, reason="response verification started"
            )
        except Exception as e:
            logger.error(f"Failed to verify session {state.session_id}: {e}", exc_info=True)
            raise

    async def complete(self, state: CognitiveState) -> None:
        try:
            await self.transition(
                state, LifecycleState.COMPLETED, reason="session completed"
            )
            await self.event_log.emit(
                EventType.SESSION_COMPLETED,
                module="runtime.lifecycle",
                session_id=state.session_id,
                state_snapshot=state.snapshot(),
            )
            logger.info(f"Session completed: {state.session_id}")
        except Exception as e:
            logger.error(f"Failed to complete session {state.session_id}: {e}", exc_info=True)
            raise

    async def fail(self, state: CognitiveState, error: str) -> None:
        try:
            with self._lock:
                self._failure_count += 1
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
            logger.error(f"Session failed: {state.session_id}, error={error[:100]}")
        except Exception as e:
            logger.error(f"Failed to fail session {state.session_id}: {e}", exc_info=True)
            raise

    async def recover(self, state: CognitiveState, reason: str) -> None:
        try:
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
            logger.info(f"Session recovery triggered: {state.session_id}, reason={reason[:100]}")
        except Exception as e:
            logger.error(f"Failed to recover session {state.session_id}: {e}", exc_info=True)
            raise

    def active_sessions(self) -> dict[str, str]:
        with self._lock:
            return dict(self._active_sessions)

    def transitions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                transition.model_dump(mode="json") for transition in self._transitions
            ]

    def get_statistics(self) -> dict[str, Any]:
        """Get lifecycle manager statistics."""
        with self._lock:
            return {
                "session_count": self._session_count,
                "failure_count": self._failure_count,
                "transition_count": self._transition_count,
                "active_sessions": len(self._active_sessions),
                "failure_rate": self._failure_count / self._session_count if self._session_count > 0 else 0,
                "total_transitions_stored": len(self._transitions),
            }
