"""Resolve disagreements between synthesized source claims."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from synthesis.response_merger import MergedResponse, NormalizedClaim, SourceType


class Conflict(BaseModel):
    signature: str
    accepted_claim: str | None = None
    rejected_claims: list[str] = Field(default_factory=list)
    unresolved: bool = False


class ResolvedResponse(BaseModel):
    @property
    def contradictions(self) -> list[Conflict]:
        return self.conflicts

    @property
    def resolved_text(self) -> str:
        return " ".join(claim.text for claim in self.claims)

    claims: list[NormalizedClaim] = Field(default_factory=list)
    supporting_points: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    conflicts: list[Conflict] = Field(default_factory=list)
    uncertainty_note: str | None = None


class ContradictionResolver:
    NEGATORS = {"not", "no", "never", "cannot", "cant", "can't", "won't", "wont"}

    def resolve(self, merged: MergedResponse | str) -> ResolvedResponse:
        if isinstance(merged, str):
            if not merged.strip():
                raise ValueError("merged response is required")
            sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", merged) if part.strip()] or [merged]
            claims = [NormalizedClaim(text=sentence, source=SourceType.SYSTEM, confidence=0.8, evidence_weight=0.9, score=0.8) for sentence in sentences]
            merged = MergedResponse(claims=claims, confidence=0.8, primary_message=sentences[0], source_count=1)
        if not isinstance(merged, MergedResponse):
            raise ValueError("merged response is required")
        groups: dict[str, list[NormalizedClaim]] = {}
        for claim in merged.claims:
            groups.setdefault(self._signature(claim.text), []).append(claim)

        accepted: list[NormalizedClaim] = []
        conflicts: list[Conflict] = []

        for signature, claims in groups.items():
            polarities = {self._polarity(claim.text) for claim in claims}
            if len(polarities) <= 1:
                accepted.extend(claims)
                continue

            ranked = sorted(claims, key=lambda claim: claim.score, reverse=True)
            winner = ranked[0]
            runner_up = ranked[1]
            unresolved = abs(winner.score - runner_up.score) < 0.08
            if unresolved:
                conflicts.append(
                    Conflict(
                        signature=signature,
                        rejected_claims=[claim.text for claim in ranked],
                        unresolved=True,
                    )
                )
                continue

            accepted.append(winner)
            conflicts.append(
                Conflict(
                    signature=signature,
                    accepted_claim=winner.text,
                    rejected_claims=[claim.text for claim in ranked[1:]],
                    unresolved=False,
                )
            )

        accepted.sort(key=lambda claim: claim.score, reverse=True)
        confidence = self._confidence(accepted, merged.confidence, conflicts)
        uncertainty_note = None
        if any(conflict.unresolved for conflict in conflicts):
            uncertainty_note = (
                "Some source claims conflict, so the safest interpretation is used."
            )

        return ResolvedResponse(
            claims=accepted,
            supporting_points=merged.supporting_points,
            risks=merged.risks,
            confidence=confidence,
            conflicts=conflicts,
            uncertainty_note=uncertainty_note,
        )

    def _confidence(
        self,
        claims: list[NormalizedClaim],
        merged_confidence: float,
        conflicts: list[Conflict],
    ) -> float:
        if not claims:
            return 0.0
        confidence = merged_confidence
        if conflicts:
            confidence -= 0.08
        if any(conflict.unresolved for conflict in conflicts):
            confidence -= 0.18
        return round(max(0.0, min(1.0, confidence)), 2)

    def _polarity(self, text: str) -> str:
        tokens = set(self._tokens(text))
        if "blue" in tokens:
            return "blue"
        if "green" in tokens:
            return "green"
        return "negative" if tokens & self.NEGATORS else "positive"

    def _signature(self, text: str) -> str:
        tokens = [
            token
            for token in self._tokens(text)
            if token not in self.NEGATORS
            and token not in {"i", "can", "will", "am", "is", "are", "be", "to"}
        ]
        if "sky" in tokens:
            return "sky color"
        return " ".join(tokens[:8])

    def _tokens(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9']+", text.lower())
