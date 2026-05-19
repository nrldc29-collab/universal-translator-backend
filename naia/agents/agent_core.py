"""Core agent models for persistent goal execution."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentState(StrEnum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"


class AgentTaskStatus(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class AgentTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str = ""
    dependencies: list[str] = Field(default_factory=list)
    status: AgentTaskStatus = AgentTaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    attempts: int = 0
    max_attempts: int = 2
    tool_request: dict[str, Any] | None = None
    assigned_agent_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)


class AgentCheckpoint(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    state: AgentState
    progress: float = Field(ge=0.0, le=1.0)
    note: str = ""


class Agent(BaseModel):
    agent_id: str = Field(default_factory=lambda: str(uuid4()))
    goal: str
    state: AgentState = AgentState.CREATED
    tasks: list[AgentTask] = Field(default_factory=list)
    memory_context: list[str] = Field(default_factory=list)
    tool_access: list[str] = Field(default_factory=list)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    parent_agent_id: str | None = None
    child_agent_ids: list[str] = Field(default_factory=list)
    last_error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    checkpoints: list[AgentCheckpoint] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def transition(self, state: AgentState, *, note: str = "") -> None:
        self.state = state
        self.touch()
        self.checkpoints.append(
            AgentCheckpoint(state=state, progress=self.progress, note=note)
        )

    def update_progress(self) -> None:
        if not self.tasks:
            self.progress = 0.0
        else:
            completed = sum(
                1
                for task in self.tasks
                if task.status
                in {
                    AgentTaskStatus.COMPLETED,
                    AgentTaskStatus.SKIPPED,
                }
            )
            self.progress = round(completed / len(self.tasks), 4)
        self.touch()

    def task_by_id(self, task_id: str) -> AgentTask | None:
        return next((task for task in self.tasks if task.task_id == task_id), None)
