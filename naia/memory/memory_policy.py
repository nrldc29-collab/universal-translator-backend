"""Policies controlling memory writes, decay, sensitivity, and approval."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryStatus(StrEnum):
    ACTIVE = "active"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PolicyAction(StrEnum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    QUARANTINE = "quarantine"
    REJECT = "reject"


class MemoryWriteCandidate(BaseModel):
    memory_type: MemoryType
    content: str
    context: str = ""
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = "system"
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryPolicyDecision(BaseModel):
    action: PolicyAction
    status: MemoryStatus
    requires_approval: bool = False
    sensitivity: str = "normal"
    reason: str = ""
    decay_rate: float = Field(default=0.01, ge=0.0, le=1.0)


class MemoryPolicyEngine:
    SENSITIVE_TERMS = {
        "api key",
        "credential",
        "password",
        "private key",
        "secret",
        "ssn",
        "social security",
        "token",
    }

    def decide_write(self, candidate: MemoryWriteCandidate) -> MemoryPolicyDecision:
        lowered = f"{candidate.content} {candidate.context}".lower()
        if not candidate.content.strip():
            return MemoryPolicyDecision(
                action=PolicyAction.REJECT,
                status=MemoryStatus.REJECTED,
                reason="empty memory content",
                decay_rate=1.0,
            )

        if any(term in lowered for term in self.SENSITIVE_TERMS):
            return MemoryPolicyDecision(
                action=PolicyAction.REQUIRE_APPROVAL,
                status=MemoryStatus.QUARANTINED,
                requires_approval=True,
                sensitivity="sensitive",
                reason="sensitive memory requires explicit approval",
                decay_rate=0.02,
            )

        if candidate.confidence < 0.35:
            return MemoryPolicyDecision(
                action=PolicyAction.QUARANTINE,
                status=MemoryStatus.QUARANTINED,
                reason="low confidence memory quarantined",
                decay_rate=0.08,
            )

        decay_rate = self.decay_rate_for(candidate)
        return MemoryPolicyDecision(
            action=PolicyAction.ALLOW,
            status=MemoryStatus.ACTIVE,
            reason="memory allowed",
            decay_rate=decay_rate,
        )

    def decay_rate_for(self, candidate: MemoryWriteCandidate) -> float:
        if candidate.importance >= 0.85 and candidate.confidence >= 0.85:
            return 0.002
        if candidate.confidence < 0.55:
            return 0.05
        if candidate.memory_type == MemoryType.EPISODIC:
            return 0.02
        return 0.01

    def can_soft_delete(self, *, reason: str) -> MemoryPolicyDecision:
        if not reason.strip():
            return MemoryPolicyDecision(
                action=PolicyAction.REJECT,
                status=MemoryStatus.ACTIVE,
                reason="memory deletion requires a reason",
            )
        return MemoryPolicyDecision(
            action=PolicyAction.ALLOW,
            status=MemoryStatus.EXPIRED,
            reason="memory soft deletion allowed",
        )
