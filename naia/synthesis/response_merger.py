"""Merge subsystem outputs into a normalized response substrate."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    TOOL = "tool"
    REASONING = "reasoning"
    MEMORY = "memory"
    PLANNER = "planner"
    AGENT = "agent"
    GOVERNANCE = "governance"
    DISPATCH = "dispatch"
    SYSTEM = "system"


SOURCE_WEIGHTS: dict[SourceType, float] = {
    SourceType.TOOL: 1.0,
    SourceType.GOVERNANCE: 0.95,
    SourceType.SYSTEM: 0.9,
    SourceType.REASONING: 0.75,
    SourceType.AGENT: 0.72,
    SourceType.PLANNER: 0.7,
    SourceType.MEMORY: 0.65,
    SourceType.DISPATCH: 0.55,
}


class SourceOutput(BaseModel):
    source: SourceType
    content: str = ""
    claims: list[str] = Field(default_factory=list)
    supporting_points: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    verified: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedClaim(BaseModel):
    text: str
    source: SourceType
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_weight: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=1.0)
    verified: bool = False


class MergedResponse(BaseModel):
    def __getitem__(self, key: str):
        if key == "content":
            return " ".join(claim.text for claim in self.claims) or self.primary_message
        if key == "metadata":
            return {}
        raise KeyError(key)

    def get(self, key: str, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    claims: list[NormalizedClaim] = Field(default_factory=list)
    supporting_points: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    primary_message: str = ""
    source_count: int = 0


class ResponseMerger:
    def merge(self, outputs: list[SourceOutput | dict]) -> MergedResponse:
        if not outputs:
            raise ValueError("outputs are required")
        outputs = [self._coerce_output(output) for output in outputs]
        claims = self._normalize_claims(outputs)
        claims = self._dedupe_claims(claims)
        claims.sort(key=lambda claim: claim.score, reverse=True)

        supporting_points = self._dedupe_text(
            point
            for output in outputs
            for point in output.supporting_points
            if point.strip()
        )
        risks = self._dedupe_text(
            risk for output in outputs for risk in output.risks if risk.strip()
        )

        confidence = self._merged_confidence(claims, outputs)
        primary_message = claims[0].text if claims else ""

        return MergedResponse(
            claims=claims,
            supporting_points=supporting_points,
            risks=risks,
            confidence=confidence,
            primary_message=primary_message,
            source_count=len(outputs),
        )

    def _coerce_output(self, output: SourceOutput | dict) -> SourceOutput:
        if isinstance(output, SourceOutput):
            return output
        if not isinstance(output, dict) or not output.get("content"):
            raise ValueError("source output content is required")
        source_value = output.get("source", SourceType.SYSTEM)
        try:
            source = SourceType(source_value)
        except ValueError:
            source = SourceType.SYSTEM
        return SourceOutput(
            source=source,
            content=str(output.get("content", "")),
            claims=[str(output.get("content", ""))],
            confidence=float(output.get("confidence", 0.5)),
        )

    def _normalize_claims(
        self, outputs: list[SourceOutput]
    ) -> list[NormalizedClaim]:
        claims: list[NormalizedClaim] = []
        for output in outputs:
            raw_claims = list(output.claims)
            if output.content.strip() and not raw_claims:
                raw_claims.append(output.content)

            for raw_claim in raw_claims:
                text = raw_claim.strip()
                if not text:
                    continue
                evidence_weight = SOURCE_WEIGHTS[output.source]
                verified_bonus = 0.08 if output.verified else 0.0
                score = min(
                    1.0,
                    output.confidence * 0.65 + evidence_weight * 0.27 + verified_bonus,
                )
                claims.append(
                    NormalizedClaim(
                        text=text,
                        source=output.source,
                        confidence=output.confidence,
                        evidence_weight=evidence_weight,
                        score=round(score, 3),
                        verified=output.verified,
                    )
                )
        return claims

    def _dedupe_claims(
        self, claims: list[NormalizedClaim]
    ) -> list[NormalizedClaim]:
        by_key: dict[str, NormalizedClaim] = {}
        for claim in claims:
            key = self._dedupe_key(claim.text)
            existing = by_key.get(key)
            if existing is None or claim.score > existing.score:
                by_key[key] = claim
        return list(by_key.values())

    def _dedupe_text(self, values) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = self._dedupe_key(value)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(value.strip())
        return deduped

    def _merged_confidence(
        self, claims: list[NormalizedClaim], outputs: list[SourceOutput]
    ) -> float:
        if claims:
            top_claims = claims[:3]
            return round(sum(claim.score for claim in top_claims) / len(top_claims), 2)
        if outputs:
            return round(
                sum(output.confidence for output in outputs) / len(outputs), 2
            )
        return 0.0

    def _dedupe_key(self, text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
