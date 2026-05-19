"""Final gate for unified identity and response synthesis."""

from __future__ import annotations

import logging
import os
from typing import Any

from pydantic import BaseModel, Field

from core import load_template

from synthesis.coherence_checker import CoherenceChecker
from synthesis.contradiction_resolver import ContradictionResolver
from synthesis.formatting_engine import FormattingEngine
from synthesis.identity_core import IdentityCore
from synthesis.response_merger import ResponseMerger, SourceOutput
from synthesis.tone_controller import ToneController

logger = logging.getLogger(__name__)


class SynthesisContext(BaseModel):
    session_id: str
    user_input: str
    task_type: str
    cognitive_mode: str
    complexity_level: str
    risk_level: str
    confidence: float


class SynthesisResult(BaseModel):
    response: str
    confidence: float = Field(ge=0.0, le=1.0)
    coherence_score: float = Field(ge=0.0, le=1.0)
    coherence_issues: list[str] = Field(default_factory=list)
    contradiction_count: int = 0
    tone_mode: str
    identity_state: dict
    source_count: int
    rewritten: bool = False


class FinalRenderer:
    """Create one coherent user-facing response from many internal sources.

    Two render paths are available:

    * ``_render_with_claude`` -- consults Anthropic's Claude API for fluent
      synthesis of the merged sources. Only invoked when ``use_claude=True``
      and ``ANTHROPIC_API_KEY`` is set and the ``anthropic`` package is
      installed. Any failure falls through to the deterministic path.
    * ``_render_with_fallback`` -- the original deterministic renderer that
      formats, checks coherence, applies tone, and sanitizes. Always
      available; used as the default and as fallback.
    """

    def __init__(
        self,
        *,
        identity_core: IdentityCore | None = None,
        merger: ResponseMerger | None = None,
        contradiction_resolver: ContradictionResolver | None = None,
        coherence_checker: CoherenceChecker | None = None,
        formatting_engine: FormattingEngine | None = None,
        tone_controller: ToneController | None = None,
        use_claude: bool = False,
        model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        self.identity_core = identity_core or IdentityCore()
        self.merger = merger or ResponseMerger()
        self.contradiction_resolver = contradiction_resolver or ContradictionResolver()
        self.coherence_checker = coherence_checker or CoherenceChecker()
        self.formatting_engine = formatting_engine or FormattingEngine()
        self.tone_controller = tone_controller or ToneController()
        self.use_claude = use_claude
        self.model = model
        self.client: Any = None

        if use_claude:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                try:
                    from anthropic import Anthropic
                    self.client = Anthropic(api_key=api_key)
                    logger.info("Final renderer initialized with Claude")
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Failed to initialize Claude for final renderer: %s", exc
                    )
                    self.client = None

    def render(
        self, outputs: list[SourceOutput] | dict, context: SynthesisContext | None = None
    ) -> SynthesisResult | str:
        if context is None:
            if not outputs:
                raise ValueError("outputs and context are required")
            return str(outputs)
        identity = self.identity_core.current_state(
            task_type=context.task_type,
            complexity_level=context.complexity_level,
            risk_level=context.risk_level,
        )
        merged = self.merger.merge(outputs)

        if self.use_claude and self.client is not None:
            claude_result = self._render_with_claude(merged, context, identity)
            if claude_result is not None:
                return claude_result

        return self._render_with_fallback(merged, context, identity)

    def _render_with_claude(
        self,
        merged: SourceOutput,
        context: SynthesisContext,
        identity: dict[str, Any],
    ) -> SynthesisResult | None:
        """Generate response using Claude with merged SourceOutputs as context."""
        try:
            sources_context = "\n\n".join(
                f"Source: {source}\nOutput: {output}"
                for source, output in zip(merged.sources, merged.outputs)
            )

            system_prompt = load_template("final_renderer")

            user_prompt = (
                f"User input: {context.user_input}\n\n"
                f"Task type: {context.task_type}\n"
                f"Complexity: {context.complexity_level}\n"
                f"Risk level: {context.risk_level}\n\n"
                f"Source outputs:\n{sources_context}\n\n"
                f"Identity state: {identity}\n\n"
                "Synthesize these sources into a coherent response to the "
                "user's input."
            )

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=0.5,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            final_text = response.content[0].text
            coherence = self.coherence_checker.check(final_text, merged)

            return SynthesisResult(
                response=final_text,
                confidence=round(max(0.0, min(1.0, context.confidence)), 2),
                coherence_score=coherence.coherence_score,
                coherence_issues=coherence.issues,
                contradiction_count=len(merged.conflicts),
                tone_mode="professional",
                identity_state=identity.model_dump() if hasattr(identity, "model_dump") else identity,
                source_count=merged.source_count,
                rewritten=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Claude rendering failed, using fallback: %s", exc)
            return None

    def _render_with_fallback(
        self,
        merged: SourceOutput,
        context: SynthesisContext,
        identity: dict[str, Any],
    ) -> SynthesisResult:
        """Original deterministic rendering pipeline."""
        resolved = self.contradiction_resolver.resolve(merged)
        draft = self.formatting_engine.format(
            resolved,
            identity,
            task_type=context.task_type,
            risk_level=context.risk_level,
            user_input=context.user_input,
        )
        coherence = self.coherence_checker.check(draft.text, resolved)
        rewritten = False

        if coherence.needs_rewrite:
            draft = self.formatting_engine.rewrite_for_coherence(
                task_type=context.task_type,
                risk_level=context.risk_level,
                user_input=context.user_input,
            )
            coherence = self.coherence_checker.check(draft.text, resolved)
            rewritten = True

        tone_mode = self.tone_controller.select_mode(
            task_type=context.task_type,
            complexity_level=context.complexity_level,
            risk_level=context.risk_level,
            identity=identity,
        )
        toned = self.tone_controller.apply(draft.text, tone_mode, identity)
        final_text = self.formatting_engine.sanitize(toned.text)
        final_coherence = self.coherence_checker.check(final_text, resolved)

        if final_coherence.needs_rewrite:
            fallback = self.formatting_engine.rewrite_for_coherence(
                task_type=context.task_type,
                risk_level=context.risk_level,
                user_input=context.user_input,
            )
            toned = self.tone_controller.apply(fallback.text, tone_mode, identity)
            final_text = self.formatting_engine.sanitize(toned.text)
            final_coherence = self.coherence_checker.check(final_text, resolved)
            rewritten = True

        confidence = min(
            context.confidence, resolved.confidence or context.confidence
        )
        if final_coherence.needs_rewrite:
            confidence = min(confidence, 0.62)

        return SynthesisResult(
            response=final_text,
            confidence=round(max(0.0, min(1.0, confidence)), 2),
            coherence_score=final_coherence.coherence_score,
            coherence_issues=final_coherence.issues,
            contradiction_count=len(resolved.conflicts),
            tone_mode=toned.tone_mode.value,
            identity_state=identity.model_dump() if hasattr(identity, "model_dump") else identity,
            source_count=merged.source_count,
            rewritten=rewritten,
        )


