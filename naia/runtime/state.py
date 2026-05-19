"""Serializable working cognition state for NAIA runtime sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class CognitiveState(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    user_input: str
    normalized_input: str = ""
    intent: str = "unknown"
    task_type: str = "unknown"
    cognitive_mode: str = "CONVERSATIONAL"
    complexity_level: str = "LOW"
    risk_level: str = "NONE"
    reasoning_depth: int = 1
    reflection_enabled: bool = False
    memory_enabled: bool = False
    tool_access: bool = False
    verification_level: str = "NONE"
    agent_activation: bool = False
    response_priority: str = "NORMAL"
    execution_budget: dict[str, Any] = Field(default_factory=dict)
    route_plan: dict[str, Any] = Field(default_factory=dict)
    synthesis: dict[str, Any] = Field(default_factory=dict)
    memory_context: str = ""
    retrieved_memories: list[dict[str, Any]] = Field(default_factory=list)
    memory_writes: list[dict[str, Any]] = Field(default_factory=list)
    tool_requests: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    agent_requests: list[dict[str, Any]] = Field(default_factory=list)
    agent_results: list[dict[str, Any]] = Field(default_factory=list)
    active_modules: list[str] = Field(default_factory=list)
    telemetry: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    lifecycle_state: str = "INITIALIZING"
    errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def add_module(self, module_name: str) -> None:
        if module_name not in self.active_modules:
            self.active_modules.append(module_name)
        self.touch()

    _MAX_ERRORS = 50

    def record_error(self, error: str) -> None:
        if len(self.errors) >= self._MAX_ERRORS:
            self.errors = self.errors[-self._MAX_ERRORS // 2:]
        self.errors.append(error)
        self.touch()

    def snapshot(self) -> dict[str, Any]:
        return self.model_dump(
            mode="json",
            include={
                "session_id",
                "intent",
                "task_type",
                "cognitive_mode",
                "complexity_level",
                "risk_level",
                "reasoning_depth",
                "reflection_enabled",
                "memory_enabled",
                "tool_access",
                "verification_level",
                "agent_activation",
                "response_priority",
                "execution_budget",
                "synthesis",
                "retrieved_memories",
                "memory_writes",
                "tool_requests",
                "tool_results",
                "agent_requests",
                "agent_results",
                "active_modules",
                "confidence",
                "lifecycle_state",
                "errors",
                "created_at",
                "updated_at",
            },
        )
