"""Models for procedural memory records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ProceduralMemory(BaseModel):
    procedure: str
    steps: list[str]
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    source: str = "unknown"
    success_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
