"""Coherence checks for synthesized responses."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from synthesis.contradiction_resolver import ResolvedResponse


INTERNAL_TERMS = {
    "active_modules",
    "cognitive router",
    "kernel",
    "module",
    "pipeline",
    "placeholder",
    "route_plan",
    "telemetry",
    "tool trace",
}


class CoherenceReport(BaseModel):
    @property
    def score(self) -> float:
        return self.coherence_score

    @property
    def is_coherent(self) -> bool:
        return not self.needs_rewrite

    coherence_score: float = Field(ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)
    needs_rewrite: bool = False


class CoherenceChecker:
    def check(self, text: str, resolved: ResolvedResponse | None = None) -> CoherenceReport:
        stripped = text.strip()
        if not stripped:
            if resolved is None:
                raise ValueError("text is required")
            return CoherenceReport(coherence_score=0.0, issues=["empty response"], needs_rewrite=True)
        if resolved is None:
            from synthesis.contradiction_resolver import ResolvedResponse
            from synthesis.response_merger import NormalizedClaim, SourceType
            resolved = ResolvedResponse(claims=[NormalizedClaim(text=stripped, source=SourceType.SYSTEM, confidence=0.8, evidence_weight=0.9, score=0.8)])
        score = 1.0
        issues: list[str] = []
        if not resolved.claims and not resolved.risks:
            score -= 0.2
            issues.append("no accepted claims")
        if any(conflict.unresolved for conflict in resolved.conflicts):
            score -= 0.18
            issues.append("unresolved contradiction")
        if self._contains_internal_terms(stripped):
            score -= 0.28
            issues.append("internal implementation detail leak")
        if self._has_repeated_sentences(stripped):
            score -= 0.12
            issues.append("repeated sentence")
        if len(stripped.split()) > 240:
            score -= 0.1
            issues.append("response too long for synthesis draft")

        score = round(max(0.0, min(1.0, score)), 2)
        return CoherenceReport(
            coherence_score=score,
            issues=issues,
            needs_rewrite=score < 0.75,
        )

    def _contains_internal_terms(self, text: str) -> bool:
        lowered = text.lower()
        return any(term in lowered for term in INTERNAL_TERMS)

    def _has_repeated_sentences(self, text: str) -> bool:
        sentences = [
            re.sub(r"[^a-z0-9]+", " ", sentence.lower()).strip()
            for sentence in re.split(r"[.!?]+", text)
            if sentence.strip()
        ]
        return len(sentences) != len(set(sentences))
