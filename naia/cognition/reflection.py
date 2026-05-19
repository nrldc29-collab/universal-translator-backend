"""Reflection module with bounded recursion for self-evaluation."""

from __future__ import annotations

import logging
import os
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ReflectionConfig(BaseModel):
    """Configuration for reflection module."""

    max_recursion_depth: int = Field(default=3, ge=1, le=10)
    min_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    enable_self_critique: bool = True
    enable_alternative_perspective: bool = True


class ReflectionResult(BaseModel):
    """Result from reflection process."""

    original_answer: str
    reflected_answer: str | None
    confidence_improvement: float = 0.0
    issues_found: list[str] = Field(default_factory=list)
    alternative_perspectives: list[str] = Field(default_factory=list)
    recursion_depth: int = 0
    should_reflect_further: bool = False


class ReflectionModule:
    """Reflection module with bounded recursion for self-evaluation."""

    def __init__(
        self,
        config: ReflectionConfig | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        api_key: str | None = None,
    ) -> None:
        """
        Initialize the reflection module.

        Args:
            config: Reflection configuration
            model: Anthropic model to use
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.config = config or ReflectionConfig()
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client: Anthropic | None = None

        if self.api_key:
            try:
                self.client = Anthropic(api_key=self.api_key)
                logger.info("Reflection module initialized with Claude")
            except Exception as exc:
                logger.warning("Failed to initialize Claude for reflection: %s", exc)
                self.client = None

    def reflect(
        self,
        original_answer: str,
        question: str,
        context: dict[str, Any] | None = None,
        current_depth: int = 0,
    ) -> ReflectionResult:
        """
        Perform reflection on an answer with bounded recursion.

        Args:
            original_answer: The original answer to reflect on
            question: The original question
            context: Additional context
            current_depth: Current recursion depth

        Returns:
            Reflection result
        """
        if current_depth >= self.config.max_recursion_depth:
            logger.warning(f"Max recursion depth {self.config.max_recursion_depth} reached")
            return ReflectionResult(
                original_answer=original_answer,
                reflected_answer=None,
                recursion_depth=current_depth,
                should_reflect_further=False,
            )

        if self.client is None:
            logger.info("Claude unavailable, returning original answer")
            return ReflectionResult(
                original_answer=original_answer,
                reflected_answer=None,
                recursion_depth=current_depth,
                should_reflect_further=False,
            )

        try:
            return self._reflect_with_claude(
                original_answer, question, context, current_depth
            )
        except Exception as exc:
            logger.warning("Claude reflection failed: %s", exc)
            return ReflectionResult(
                original_answer=original_answer,
                reflected_answer=None,
                recursion_depth=current_depth,
                should_reflect_further=False,
            )

    def _reflect_with_claude(
        self,
        original_answer: str,
        question: str,
        context: dict[str, Any] | None,
        current_depth: int,
    ) -> ReflectionResult:
        """Perform reflection using Claude."""
        context_str = "\n".join([f"{k}: {v}" for k, v in (context or {}).items()])

        system_prompt = f"""You are NAIA's reflection module. Your task is to critically evaluate your own answers and suggest improvements.

Guidelines:
- Identify any errors, inconsistencies, or gaps in the original answer
- Consider alternative perspectives or approaches
- Suggest improvements while maintaining the original intent
- Be concise and specific

Max recursion depth: {self.config.max_recursion_depth}
Current depth: {current_depth}

Provide your reflection in the following JSON format:
{{
  "issues_found": ["issue1", "issue2"],
  "alternative_perspectives": ["perspective1", "perspective2"],
  "improved_answer": "<improved version if needed, or null if original is good>",
  "confidence_score": <0.0-1.0>,
  "should_reflect_further": true/false
}}"""

        user_prompt = f"""Question: {question}

Original answer:
{original_answer}

Context:
{context_str if context_str else "No additional context"}

Reflect on this answer and provide your analysis in JSON format."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0.3,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text

        # Extract JSON from response
        import json
        import re

        json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
        if json_match:
            result_data = json.loads(json_match.group())
        else:
            result_data = json.loads(content)

        improved_answer = result_data.get("improved_answer")
        confidence_score = result_data.get("confidence_score", 0.7)
        should_reflect_further = result_data.get("should_reflect_further", False)

        # Check if we should recurse further
        if should_reflect_further and current_depth < self.config.max_recursion_depth - 1:
            if improved_answer:
                # Recurse on the improved answer
                deeper_reflection = self.reflect(
                    improved_answer, question, context, current_depth + 1
                )
                return ReflectionResult(
                    original_answer=original_answer,
                    reflected_answer=deeper_reflection.reflected_answer,
                    confidence_improvement=deeper_reflection.confidence_improvement,
                    issues_found=result_data.get("issues_found", []),
                    alternative_perspectives=result_data.get("alternative_perspectives", []),
                    recursion_depth=deeper_reflection.recursion_depth,
                    should_reflect_further=False,  # Stopped after bounded recursion
                )

        return ReflectionResult(
            original_answer=original_answer,
            reflected_answer=improved_answer,
            confidence_improvement=confidence_score - 0.5,  # Baseline improvement
            issues_found=result_data.get("issues_found", []),
            alternative_perspectives=result_data.get("alternative_perspectives", []),
            recursion_depth=current_depth,
            should_reflect_further=should_reflect_further,
        )

    def quick_reflection(self, answer: str, question: str) -> str:
        """
        Perform a single-pass reflection without recursion.

        Args:
            answer: The answer to reflect on
            question: The original question

        Returns:
            Reflected answer or original if no improvement
        """
        result = self.reflect(answer, question, current_depth=0)
        return result.reflected_answer if result.reflected_answer else result.original_answer

    def is_available(self) -> bool:
        """Check if reflection module is available."""
        return self.client is not None
