"""Models for episodic memory records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class EpisodicMemory(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str
    event: str
    context: str
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
