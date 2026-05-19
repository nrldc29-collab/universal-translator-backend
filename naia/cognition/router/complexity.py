"""Complexity estimation for cognitive routing."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from cognition.router.classifier import TaskClassification, TaskClassifier, TaskType
from cognition.router.modes import CognitiveMode


class ComplexityLevel(StrEnum):
    MINIMAL = "MINIMAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class ComplexityAssessment(BaseModel):
    complexity: ComplexityLevel
    estimated_reasoning_depth: int = Field(ge=1, le=5)
    recommended_mode: CognitiveMode
    factors: dict[str, Any] = Field(default_factory=dict)


class ComplexityEstimator:
    TASK_WEIGHTS: dict[TaskType, int] = {
        TaskType.CONVERSATION: 0,
        TaskType.CODING: 2,
        TaskType.RESEARCH: 3,
        TaskType.PLANNING: 3,
        TaskType.CREATIVE: 1,
        TaskType.REASONING: 2,
        TaskType.AUTOMATION: 2,
        TaskType.MATH: 3,
        TaskType.ANALYSIS: 3,
    }

    COMPLEXITY_TERMS = {
        "adaptive",
        "architecture",
        "autonomous",
        "cognition",
        "distributed",
        "governance",
        "kernel",
        "multi-step",
        "operating system",
        "orchestrate",
        "pipeline",
        "scalable",
        "security",
        "stability",
    }

    UNCERTAINTY_TERMS = {
        "ambiguous",
        "maybe",
        "not sure",
        "unknown",
        "unclear",
        "what if",
        "whether",
    }

    def estimate(
        self, user_input: str, classification: TaskClassification
    ) -> ComplexityAssessment:
        text = " ".join(user_input.lower().strip().split())
        word_count = len(text.split())
        dependency_count = self._dependency_count(text)
        uncertainty_count = sum(term in text for term in self.UNCERTAINTY_TERMS)
        complexity_terms = sum(term in text for term in self.COMPLEXITY_TERMS)

        score = 0
        score += self._length_score(word_count)
        score += self.TASK_WEIGHTS[classification.task_type]
        score += min(dependency_count, 4)
        score += min(uncertainty_count, 3)
        score += min(complexity_terms, 5)

        level = self._level_from_score(score, word_count)
        depth = self._depth_from_level(level)
        mode = self._recommended_mode(level, classification.task_type)

        return ComplexityAssessment(
            complexity=level,
            estimated_reasoning_depth=depth,
            recommended_mode=mode,
            factors={
                "score": score,
                "word_count": word_count,
                "task_weight": self.TASK_WEIGHTS[classification.task_type],
                "dependency_count": dependency_count,
                "uncertainty_count": uncertainty_count,
                "complexity_terms": complexity_terms,
            },
        )

    def _length_score(self, word_count: int) -> int:
        if word_count <= 3:
            return 0
        if word_count <= 20:
            return 1
        if word_count <= 80:
            return 2
        if word_count <= 180:
            return 3
        return 4

    def _dependency_count(self, text: str) -> int:
        connectors = len(re.findall(r"\b(and|then|also|while|plus|with)\b", text))
        numbered_steps = len(re.findall(r"\b\d+[\.\)]", text))
        bullet_like = text.count("- ")
        return connectors + numbered_steps + bullet_like

    def _level_from_score(self, score: int, word_count: int) -> ComplexityLevel:
        if word_count <= 3 and score <= 1:
            return ComplexityLevel.MINIMAL
        if score <= 2:
            return ComplexityLevel.LOW
        if score <= 5:
            return ComplexityLevel.MEDIUM
        if score <= 9:
            return ComplexityLevel.HIGH
        return ComplexityLevel.EXTREME

    def _depth_from_level(self, level: ComplexityLevel) -> int:
        return {
            ComplexityLevel.MINIMAL: 1,
            ComplexityLevel.LOW: 2,
            ComplexityLevel.MEDIUM: 3,
            ComplexityLevel.HIGH: 4,
            ComplexityLevel.EXTREME: 5,
        }[level]

    def _recommended_mode(
        self, level: ComplexityLevel, task_type: TaskType
    ) -> CognitiveMode:
        if task_type == TaskType.RESEARCH:
            return CognitiveMode.RESEARCH
        if task_type in {TaskType.CODING, TaskType.AUTOMATION}:
            return CognitiveMode.EXECUTION
        if level == ComplexityLevel.MINIMAL:
            return CognitiveMode.REFLEX
        if level == ComplexityLevel.LOW:
            return CognitiveMode.CONVERSATIONAL
        return CognitiveMode.ANALYTICAL


class LegacyComplexityResult(BaseModel):
    level: str
    score: float


class ComplexityAnalyzer:
    def __init__(self) -> None:
        self._classifier = TaskClassifier()
        self._estimator = ComplexityEstimator()

    def analyze(self, user_input: str) -> LegacyComplexityResult:
        if not user_input.strip():
            raise ValueError("user_input is required")
        classification = self._classifier.classify(user_input)
        result = self._estimator.estimate(user_input, classification)
        return LegacyComplexityResult(level=result.complexity.value, score=float(result.factors.get("score", 0)))
