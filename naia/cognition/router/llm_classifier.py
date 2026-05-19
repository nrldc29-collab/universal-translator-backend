"""LLM-based classifier using Anthropic Claude for intent/complexity/risk classification.

This provides higher-quality classification than the regex-based fallback, with graceful
degradation to maintain constitutional invariant 9 (fail gracefully).
"""

from __future__ import annotations

import logging
import os
from enum import StrEnum
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class Intent(StrEnum):
    QUERY = "query"
    TASK = "task"
    CODE = "code"
    PLANNING = "planning"
    MEMORY = "memory"
    SYNTHESIS = "synthesis"
    FAILURE = "failure"


class Complexity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Risk(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class LLMClassificationResult(BaseModel):
    """Result from LLM-based classification."""

    intent: Intent
    complexity: Complexity
    risk: Risk
    confidence: float = Field(ge=0.0, le=1.0)
    requires_tools: bool = False
    requires_memory: bool = False
    reasoning: str = ""


class LLMClassifier:
    """LLM-based classifier using Anthropic Claude.

    Falls back to regex-based classification if Claude is unavailable or fails,
    maintaining constitutional invariant 9 (fail gracefully).
    """

    def __init__(self, model: str = "claude-3-5-sonnet-20241022", api_key: str | None = None) -> None:
        """
        Initialize the LLM classifier.

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
                logger.info("LLM classifier initialized with Anthropic Claude")
            except Exception as exc:
                logger.warning("Failed to initialize Anthropic client: %s", exc)
                self.client = None

    def classify(self, user_input: str, context: dict[str, Any] | None = None) -> LLMClassificationResult:
        """
        Classify user input using LLM with fallback to regex.

        Args:
            user_input: The user's input text
            context: Additional context for classification

        Returns:
            Classification result
        """
        if self.client is None:
            logger.info("LLM client unavailable, using fallback classification")
            return self._fallback_classification(user_input)

        try:
            return self._classify_with_llm(user_input, context or {})
        except Exception as exc:
            logger.warning("LLM classification failed, using fallback: %s", exc)
            return self._fallback_classification(user_input)

    def _classify_with_llm(self, user_input: str, context: dict[str, Any]) -> LLMClassificationResult:
        """Classify using Anthropic Claude."""
        system_prompt = """You are NAIA's intent classifier. Analyze the user's input and classify it by intent, complexity, and risk level.

Intent categories:
- query: A question seeking information
- task: A request to perform an action or computation
- code: A request related to programming or code execution
- planning: A request that requires multi-step reasoning or planning
- memory: A request related to recalling or storing information
- synthesis: A request to combine or summarize information
- failure: An indication of error or failure

Complexity levels:
- low: Simple, straightforward, can be answered directly
- medium: Requires some reasoning or multiple steps
- high: Complex, requires significant reasoning or planning
- critical: Extremely complex or high-stakes

Risk levels:
- LOW: No significant risk
- MEDIUM: Moderate risk, requires attention
- HIGH: High risk, requires careful consideration
- CRITICAL: Critical risk, requires human approval

Be conservative with risk assessment. Provide confidence between 0.0 and 1.0."""

        user_prompt = f"""User input: {user_input}

Context: {context}

Provide your classification in the following JSON format:
{{
  "intent": "<intent>",
  "complexity": "<complexity>",
  "risk": "<risk>",
  "confidence": <0.0-1.0>,
  "requires_tools": true|false,
  "requires_memory": true|false,
  "reasoning": "<brief explanation>"
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
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
                return LLMClassificationResult(**result_data)

            # Fallback: try parsing entire response
            return LLMClassificationResult(**json.loads(content))

        except (json.JSONDecodeError, ValidationError, KeyError) as exc:
            logger.warning("Failed to parse LLM response: %s", exc)
            raise

    def _fallback_classification(self, user_input: str) -> LLMClassificationResult:
        """Fallback classification using simple heuristics."""
        lowered = user_input.lower()

        # Intent detection
        if any(term in lowered for term in ["?", "what", "how", "why", "explain"]):
            intent = Intent.QUERY
        elif any(term in lowered for term in ["calculate", "compute", "run", "execute"]):
            intent = Intent.TASK
        elif any(term in lowered for term in ["code", "function", "class", "bug"]):
            intent = Intent.CODE
        elif any(term in lowered for term in ["plan", "design", "architecture"]):
            intent = Intent.PLANNING
        elif any(term in lowered for term in ["remember", "previous", "earlier"]):
            intent = Intent.MEMORY
        elif any(term in lowered for term in ["summarize", "combine", "merge"]):
            intent = Intent.SYNTHESIS
        elif any(term in lowered for term in ["error", "failed", "broken"]):
            intent = Intent.FAILURE
        else:
            intent = Intent.QUERY

        # Complexity detection
        if len(user_input.split()) < 10:
            complexity = Complexity.LOW
        elif len(user_input.split()) < 30:
            complexity = Complexity.MEDIUM
        elif len(user_input.split()) < 50:
            complexity = Complexity.HIGH
        else:
            complexity = Complexity.CRITICAL

        # Risk detection
        risk_terms = {
            Risk.CRITICAL: ["delete", "destroy", "format", "wipe", "shutdown"],
            Risk.HIGH: ["password", "secret", "token", "private key"],
            Risk.MEDIUM: ["file", "directory", "network", "url"],
        }

        risk = Risk.LOW
        for risk_level, terms in risk_terms.items():
            if any(term in lowered for term in terms):
                risk = risk_level
                break

        # Tool/memory requirements
        requires_tools = any(
            term in lowered
            for term in ["execute", "run", "file", "directory", "search", "fetch"]
        )
        requires_memory = any(
            term in lowered for term in ["remember", "previous", "earlier", "context"]
        )

        return LLMClassificationResult(
            intent=intent,
            complexity=complexity,
            risk=risk,
            confidence=0.5,  # Lower confidence for fallback
            requires_tools=requires_tools,
            requires_memory=requires_memory,
            reasoning="Fallback classification using heuristics",
        )

    def is_available(self) -> bool:
        """Check if LLM classifier is available."""
        return self.client is not None
