"""Reasoning module for deep cognitive analysis using Claude."""

from __future__ import annotations

import logging
import os
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ReasoningResult(BaseModel):
    """Result from the reasoning module."""

    analysis: str
    conclusion: str
    confidence: float = Field(ge=0.0, le=1.0)
    assumptions: list[str] = Field(default_factory=list)
    alternatives_considered: list[str] = Field(default_factory=list)
    reasoning_steps: list[str] = Field(default_factory=list)


class ReasoningModule:
    """Reasoning module using Claude for deep cognitive analysis."""

    def __init__(self, model: str = "claude-3-5-sonnet-20241022", api_key: str | None = None) -> None:
        """
        Initialize the reasoning module.

        Args:
            model: Anthropic model to use
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client: Anthropic | None = None

        if self.api_key:
            try:
                self.client = Anthropic(api_key=self.api_key)
                logger.info("Reasoning module initialized with Claude")
            except Exception as exc:
                logger.warning("Failed to initialize Claude for reasoning: %s", exc)
                self.client = None

    def reason(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        max_depth: int = 3,
    ) -> ReasoningResult:
        """
        Perform deep reasoning on a query.

        Args:
            query: The query to reason about
            context: Additional context for reasoning
            max_depth: Maximum reasoning depth (bounded recursion)

        Returns:
            Reasoning result
        """
        if self.client is None:
            logger.info("Reasoning client unavailable, using shallow reasoning")
            return self._shallow_reasoning(query, context)

        try:
            return self._reason_with_claude(query, context, max_depth)
        except Exception as exc:
            logger.warning("Claude reasoning failed, using shallow: %s", exc)
            return self._shallow_reasoning(query, context)

    def _reason_with_claude(
        self,
        query: str,
        context: dict[str, Any] | None,
        max_depth: int,
    ) -> ReasoningResult:
        """Reason using Claude."""
        context_str = "\n".join([f"{k}: {v}" for k, v in (context or {}).items()])

        system_prompt = f"""You are NAIA's reasoning module. Perform deep cognitive analysis on the user's query.

Your analysis should:
1. Break down the query into components
2. Identify assumptions and constraints
3. Consider alternative interpretations
4. Provide step-by-step reasoning
5. Reach a well-supported conclusion

Keep reasoning bounded to {max_depth} levels of depth. Be thorough but concise.

Provide your response in the following JSON format:
{{
  "analysis": "<detailed analysis>",
  "conclusion": "<main conclusion>",
  "confidence": <0.0-1.0>,
  "assumptions": ["<assumption1>", "<assumption2>"],
  "alternatives_considered": ["<alternative1>", "<alternative2>"],
  "reasoning_steps": ["<step1>", "<step2>", "<step3>"]
}}"""

        user_prompt = f"""Query: {query}

Context:
{context_str if context_str else "No additional context"}

Provide your reasoning analysis in JSON format."""

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

        return ReasoningResult(**result_data)

    def _shallow_reasoning(
        self,
        query: str,
        context: dict[str, Any] | None,
    ) -> ReasoningResult:
        """Fallback shallow reasoning without LLM."""
        analysis = f"Query: {query}\n"
        if context:
            analysis += f"Context: {context}\n"
        analysis += "Note: Using shallow reasoning (LLM unavailable)"

        return ReasoningResult(
            analysis=analysis,
            conclusion="Unable to perform deep analysis without LLM",
            confidence=0.3,
            assumptions=["LLM reasoning unavailable"],
            alternatives_considered=["Direct execution", "Manual analysis"],
            reasoning_steps=["Parse query", "Check context", "Return limited analysis"],
        )

    def is_available(self) -> bool:
        """Check if reasoning module is available."""
        return self.client is not None
