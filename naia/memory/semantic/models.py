"""Models for semantic memory records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class SemanticMemory(BaseModel):
    fact: str
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    source: str = "unknown"
    last_verified: datetime | None = None
    requires_approval: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
