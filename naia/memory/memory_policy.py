"""Policies controlling memory writes, decay, sensitivity, and approval."""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


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

    def __init__(self) -> None:
        self._decision_count = 0
        self._reject_count = 0
        self._quarantine_count = 0
        self._approve_count = 0
        logger.info("MemoryPolicyEngine initialized")

    def decide_write(self, candidate: MemoryWriteCandidate) -> MemoryPolicyDecision:
        """Decide whether to allow, quarantine, or reject a memory write."""
        self._decision_count += 1
        try:
            lowered = f"{candidate.content} {candidate.context}".lower()
            if not candidate.content.strip():
                self._reject_count += 1
                logger.debug(f"Memory rejected: empty content")
                return MemoryPolicyDecision(
                    action=PolicyAction.REJECT,
                    status=MemoryStatus.REJECTED,
                    reason="empty memory content",
                    decay_rate=1.0,
                )

            if any(term in lowered for term in self.SENSITIVE_TERMS):
                self._quarantine_count += 1
                logger.warning(f"Memory quarantined: sensitive terms detected in {candidate.memory_type}")
                return MemoryPolicyDecision(
                    action=PolicyAction.REQUIRE_APPROVAL,
                    status=MemoryStatus.QUARANTINED,
                    requires_approval=True,
                    sensitivity="sensitive",
                    reason="sensitive memory requires explicit approval",
                    decay_rate=0.02,
                )

            if candidate.confidence < 0.35:
                self._quarantine_count += 1
                logger.debug(f"Memory quarantined: low confidence ({candidate.confidence})")
                return MemoryPolicyDecision(
                    action=PolicyAction.QUARANTINE,
                    status=MemoryStatus.QUARANTINED,
                    reason="low confidence memory quarantined",
                    decay_rate=0.08,
                )

            decay_rate = self.decay_rate_for(candidate)
            self._approve_count += 1
            logger.debug(f"Memory allowed: {candidate.memory_type}, confidence={candidate.confidence}")
            return MemoryPolicyDecision(
                action=PolicyAction.ALLOW,
                status=MemoryStatus.ACTIVE,
                reason="memory allowed",
                decay_rate=decay_rate,
            )
        except Exception as e:
            logger.error(f"Memory policy decision failed: {e}", exc_info=True)
            # Fail-safe: quarantine on error
            self._quarantine_count += 1
            return MemoryPolicyDecision(
                action=PolicyAction.QUARANTINE,
                status=MemoryStatus.QUARANTINED,
                reason=f"policy error: {str(e)[:100]}",
                decay_rate=0.1,
            )

    def decay_rate_for(self, candidate: MemoryWriteCandidate) -> float:
        """Calculate decay rate based on memory importance and confidence."""
        if candidate.importance >= 0.85 and candidate.confidence >= 0.85:
            return 0.002
        if candidate.confidence < 0.55:
            return 0.05
        if candidate.memory_type == MemoryType.EPISODIC:
            return 0.02
        return 0.01

    def can_soft_delete(self, *, reason: str) -> MemoryPolicyDecision:
        """Decide whether a memory can be soft deleted."""
        try:
            if not reason.strip():
                logger.warning("Memory soft delete rejected: no reason provided")
                return MemoryPolicyDecision(
                    action=PolicyAction.REJECT,
                    status=MemoryStatus.ACTIVE,
                    reason="memory deletion requires a reason",
                )
            logger.debug(f"Memory soft delete allowed: reason={reason[:50]}")
            return MemoryPolicyDecision(
                action=PolicyAction.ALLOW,
                status=MemoryStatus.EXPIRED,
                reason="memory soft deletion allowed",
            )
        except Exception as e:
            logger.error(f"Soft delete policy check failed: {e}", exc_info=True)
            return MemoryPolicyDecision(
                action=PolicyAction.REJECT,
                status=MemoryStatus.ACTIVE,
                reason=f"policy error: {str(e)[:100]}",
            )

    def get_statistics(self) -> dict[str, Any]:
        """Get policy engine statistics."""
        return {
            "decision_count": self._decision_count,
            "reject_count": self._reject_count,
            "quarantine_count": self._quarantine_count,
            "approve_count": self._approve_count,
            "reject_rate": self._reject_count / self._decision_count if self._decision_count > 0 else 0,
            "quarantine_rate": self._quarantine_count / self._decision_count if self._decision_count > 0 else 0,
            "approve_rate": self._approve_count / self._decision_count if self._decision_count > 0 else 0,
            "sensitive_terms_count": len(self.SENSITIVE_TERMS),
        }
