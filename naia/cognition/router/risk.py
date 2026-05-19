"""Risk estimation for the cognitive routing engine."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from cognition.router.classifier import TaskClassification


class RiskLevel(StrEnum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskAssessment(BaseModel):
    risk: RiskLevel

    @property
    def level(self) -> RiskLevel:
        return RiskLevel.LOW if self.risk == RiskLevel.NONE else self.risk
    requires_confirmation: bool
    restricted_tools: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    factors: dict[str, Any] = Field(default_factory=dict)


class RiskEngine:
    DESTRUCTIVE_TERMS = {
        "delete",
        "destroy",
        "drop database",
        "format",
        "remove all",
        "reset hard",
        "shutdown",
        "wipe",
    }
    CRITICAL_DESTRUCTIVE_TERMS = {
        "delete everything",
        "drop production",
        "format drive",
        "wipe disk",
        "wipe everything",
    }
    FINANCIAL_TERMS = {
        "buy",
        "invoice",
        "pay",
        "purchase",
        "sell",
        "transfer money",
        "wire funds",
    }
    SECURITY_TERMS = {
        "credential",
        "exploit",
        "password",
        "private key",
        "secret",
        "token",
        "vulnerability",
    }
    PRIVACY_TERMS = {
        "personal data",
        "private information",
        "social security",
        "ssn",
    }
    EXTERNAL_TERMS = {
        "email",
        "message them",
        "post",
        "publish",
        "send message",
        "tweet",
    }
    DEPLOYMENT_TERMS = {
        "deploy",
        "production",
        "release",
        "rollout",
    }

    def estimate(
        self, user_input: str, classification: TaskClassification
    ) -> RiskAssessment:
        text = " ".join(user_input.lower().strip().split())
        reasons: list[str] = []
        restricted_tools: set[str] = set()
        score = 0

        if any(term in text for term in self.CRITICAL_DESTRUCTIVE_TERMS):
            score += 5
            reasons.append("critical destructive operation language detected")
            restricted_tools.update({"shell", "filesystem"})
        elif any(term in text for term in self.DESTRUCTIVE_TERMS):
            score += 3
            reasons.append("destructive operation language detected")
            restricted_tools.update({"shell", "filesystem"})

        if any(term in text for term in self.FINANCIAL_TERMS):
            score += 4
            reasons.append("financial impact language detected")
            restricted_tools.add("financial")

        if any(term in text for term in self.SECURITY_TERMS):
            score += 2
            reasons.append("security-sensitive language detected")
            restricted_tools.update({"shell", "network"})

        if any(term in text for term in self.PRIVACY_TERMS):
            score += 2
            reasons.append("privacy exposure language detected")
            restricted_tools.add("external_api")

        if any(term in text for term in self.EXTERNAL_TERMS):
            score += 3
            reasons.append("external communication language detected")
            restricted_tools.add("external_communication")

        if any(term in text for term in self.DEPLOYMENT_TERMS):
            score += 3
            reasons.append("deployment or release language detected")
            restricted_tools.add("deployment")

        if classification.requires_tools and not reasons:
            score += 1
            reasons.append("tool usage requested")

        risk = self._risk_from_score(score)
        return RiskAssessment(
            risk=risk,
            requires_confirmation=risk in {RiskLevel.HIGH, RiskLevel.CRITICAL},
            restricted_tools=sorted(restricted_tools),
            reasons=reasons,
            factors={
                "score": score,
                "requires_tools": classification.requires_tools,
                "execution_requirements": classification.execution_requirements,
            },
        )

    def _risk_from_score(self, score: int) -> RiskLevel:
        if score <= 0:
            return RiskLevel.NONE
        if score == 1:
            return RiskLevel.LOW
        if score == 2:
            return RiskLevel.MEDIUM
        if score <= 5:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL

