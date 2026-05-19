"""Convert resolved content into clean user-facing structure."""

from __future__ import annotations

import re

from pydantic import BaseModel

from synthesis.contradiction_resolver import ResolvedResponse
from synthesis.identity_core import IdentityState


INTERNAL_SENTENCE_TERMS = {
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


class FormattedDraft(BaseModel):
    text: str


class FormattingEngine:
    def format(
        self,
        resolved: ResolvedResponse | str,
        identity: IdentityState | None = None,
        *,
        task_type: str = "conversation",
        risk_level: str = "NONE",
        user_input: str = "",
        format_type: str | None = None,
    ) -> FormattedDraft | str:
        if isinstance(resolved, str):
            if format_type not in {None, "plain"}:
                raise ValueError("unknown format type")
            return self.sanitize(resolved)
        if risk_level in {"HIGH", "CRITICAL"}:
            text = self._format_high_risk(resolved)
        elif task_type == "conversation" and len(user_input.split()) <= 3:
            text = self._format_reflex(resolved)
        elif identity.verbosity == "structured":
            text = self._format_structured(resolved, task_type)
        else:
            text = self._format_plain(resolved, task_type)

        return FormattedDraft(text=self.sanitize(text))

    def rewrite_for_coherence(
        self,
        *,
        task_type: str,
        risk_level: str,
        user_input: str,
    ) -> FormattedDraft:
        if risk_level in {"HIGH", "CRITICAL"}:
            text = (
                "I cannot carry out that action without explicit human approval. "
                "I can help make it safer by clarifying scope, reversibility, "
                "and review steps first."
            )
        elif task_type == "conversation" and len(user_input.split()) <= 3:
            text = "Hi. I am here."
        else:
            text = (
                "I can help with that. I will keep the response clear, "
                "consistent, and focused on the request."
            )
        return FormattedDraft(text=text)

    def sanitize(self, text: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        clean_sentences = [
            sentence.strip()
            for sentence in sentences
            if sentence.strip()
            and not any(term in sentence.lower() for term in INTERNAL_SENTENCE_TERMS)
        ]
        clean = " ".join(clean_sentences)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def _format_high_risk(self, resolved: ResolvedResponse) -> str:
        primary = self._primary_claim(resolved)
        safety = (
            "I can help make the request safer by clarifying intent, scope, "
            "reversibility, and approval requirements first."
        )
        if primary:
            return f"{primary} {safety}"
        return (
            "I cannot carry out that action without explicit human approval. "
            f"{safety}"
        )

    def _format_reflex(self, resolved: ResolvedResponse) -> str:
        primary = self._primary_claim(resolved)
        return primary or "Hi. I am here."

    def _format_plain(self, resolved: ResolvedResponse, task_type: str) -> str:
        primary = self._primary_claim(resolved)
        if not primary:
            return (
                "I can help with that. I will keep the response clear and focused."
            )
        return primary

    def _format_structured(
        self, resolved: ResolvedResponse, task_type: str
    ) -> str:
        primary = self._primary_claim(resolved)
        if not primary:
            return (
                "I can help with that. I will keep the response structured and "
                "easy to review."
            )

        points = [
            point
            for point in resolved.supporting_points
            if point.strip() and point.strip() != primary
        ][:3]
        if not points:
            return primary

        formatted_points = " ".join(f"{index}. {point}" for index, point in enumerate(points, 1))
        return f"{primary} {formatted_points}"

    def _primary_claim(self, resolved: ResolvedResponse) -> str:
        if resolved.claims:
            return resolved.claims[0].text
        if resolved.uncertainty_note:
            return resolved.uncertainty_note
        return ""
