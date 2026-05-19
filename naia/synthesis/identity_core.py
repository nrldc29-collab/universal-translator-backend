"""Stable identity constraints for final response synthesis."""

from __future__ import annotations

from pydantic import BaseModel


class IdentityState(BaseModel):
    tone: str = "neutral-clear"
    verbosity: str = "adaptive"
    reasoning_style: str = "structured"
    safety_level: str = "governed"
    consistency_lock: bool = True


class IdentityCore:
    """Output consistency enforcement, not personality simulation."""

    def current_state(
        self,
        *,
        task_type: str = "conversation",
        complexity_level: str = "LOW",
        risk_level: str = "NONE",
    ) -> IdentityState:
        verbosity = "adaptive"
        if complexity_level == "MINIMAL":
            verbosity = "concise"
        elif complexity_level in {"HIGH", "EXTREME"}:
            verbosity = "structured"

        safety_level = "governed"
        if risk_level in {"HIGH", "CRITICAL"}:
            safety_level = "strict-governed"

        reasoning_style = "structured"
        if task_type == "conversation":
            reasoning_style = "direct"
        elif task_type in {"analysis", "planning", "reasoning"}:
            reasoning_style = "structured"

        return IdentityState(
            tone="neutral-clear",
            verbosity=verbosity,
            reasoning_style=reasoning_style,
            safety_level=safety_level,
            consistency_lock=True,
        )
