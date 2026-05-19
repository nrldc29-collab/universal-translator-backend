"""Apply final tone constraints without changing factual content."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from synthesis.identity_core import IdentityState


class ToneMode(StrEnum):
    DEFAULT = "DEFAULT"
    TECHNICAL = "TECHNICAL"
    EXPLANATORY = "EXPLANATORY"
    CONCISE = "CONCISE"
    DETAILED = "DETAILED"


class ToneResult(BaseModel):
    text: str
    tone_mode: ToneMode


class ToneController:
    def adjust_tone(self, text: str, tone: str = "professional") -> str:
        allowed = {"professional", "friendly", "casual", "formal", "concise", "technical"}
        if tone not in allowed:
            raise ValueError("unknown tone")
        if tone == "concise":
            return self._first_sentence(text)
        if tone == "casual":
            return self._ensure_period(f"Sure - {text.strip()}")
        if tone == "formal":
            return self._ensure_period(f"Please note: {text.strip()}")
        return self._ensure_period(text.strip())

    def select_mode(
        self,
        *,
        task_type: str,
        complexity_level: str,
        risk_level: str,
        identity: IdentityState,
    ) -> ToneMode:
        if risk_level in {"HIGH", "CRITICAL"}:
            return ToneMode.DEFAULT
        if complexity_level == "MINIMAL":
            return ToneMode.CONCISE
        if task_type in {"coding", "analysis", "math"}:
            return ToneMode.TECHNICAL
        if task_type in {"reasoning", "planning", "research"}:
            return ToneMode.EXPLANATORY
        if complexity_level in {"HIGH", "EXTREME"}:
            return ToneMode.DETAILED
        return ToneMode.DEFAULT

    def apply(self, text: str, tone_mode: ToneMode, identity: IdentityState) -> ToneResult:
        clean = text.strip()
        if not clean:
            clean = "I can help with that."

        if tone_mode == ToneMode.CONCISE:
            clean = self._first_sentence(clean)
        elif tone_mode == ToneMode.TECHNICAL:
            clean = self._ensure_period(clean)
        elif tone_mode == ToneMode.EXPLANATORY:
            clean = self._ensure_period(clean)
        elif tone_mode == ToneMode.DETAILED:
            clean = self._ensure_period(clean)
        else:
            clean = self._ensure_period(clean)

        return ToneResult(text=clean, tone_mode=tone_mode)

    def _first_sentence(self, text: str) -> str:
        for marker in [". ", "? ", "! "]:
            if marker in text:
                return self._ensure_period(text.split(marker, 1)[0])
        return self._ensure_period(text)

    def _ensure_period(self, text: str) -> str:
        if text.endswith((".", "?", "!")):
            return text
        return f"{text}."
