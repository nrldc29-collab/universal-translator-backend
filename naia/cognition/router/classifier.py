"""Task classification for the cognitive routing engine.

Two backends share a single public surface:

* ``_classify_with_keywords`` -- deterministic, no dependencies, always
  available. Identical to the original NAIA v0.2 classifier.
* ``_classify_with_llm`` -- consults the local GGUF model via
  ``core.model_client.get_global_client``. Higher quality but only
  available when the model layer is initialized.

The LLM path is opt-in (``use_local_model=True``). Any failure inside it
falls back to the keyword path silently so the router never breaks just
because the model is missing -- per constitutional invariant 9 (fail
gracefully).
"""

from __future__ import annotations

import logging
import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from core import load_template

logger = logging.getLogger(__name__)


class TaskType(StrEnum):
    CONVERSATION = "conversation"
    CODING = "coding"
    RESEARCH = "research"
    PLANNING = "planning"
    CREATIVE = "creative"
    REASONING = "reasoning"
    AUTOMATION = "automation"
    MATH = "math"
    ANALYSIS = "analysis"


TASK_TYPES = [task_type.value for task_type in TaskType]


class TaskClassification(BaseModel):
    task_type: TaskType
    confidence: float = Field(ge=0.0, le=1.0)
    requires_tools: bool
    requires_memory: bool
    domain: str | None = None
    urgency: str = "normal"
    execution_requirements: list[str] = Field(default_factory=list)
    signals: dict[str, Any] = Field(default_factory=dict)


class TaskClassifier:
    """Task classifier with optional LLM augmentation."""

    def __init__(self, use_local_model: bool = False) -> None:
        self.use_local_model = use_local_model

    KEYWORDS: dict[TaskType, set[str]] = {
        TaskType.CONVERSATION: {"hi", "hello", "hey", "thanks", "thank you", "how are you"},
        TaskType.CODING: {
            "api", "bug", "class", "code", "debug", "fastapi", "fix", "function",
            "implement", "python", "refactor", "test",
        },
        TaskType.RESEARCH: {
            "cite", "evidence", "find", "latest", "lookup", "paper", "research",
            "source", "verify online",
        },
        TaskType.PLANNING: {
            "architecture", "design", "milestone", "plan", "roadmap", "schedule",
            "strategy", "timeline",
        },
        TaskType.CREATIVE: {
            "brainstorm", "concept", "creative", "draft", "image", "story", "write",
        },
        TaskType.REASONING: {"compare", "explain", "reason", "tradeoff", "why"},
        TaskType.AUTOMATION: {
            "automate", "cron", "monitor", "remind", "schedule job", "watch",
        },
        TaskType.MATH: {
            "calculate", "equation", "math", "probability", "solve", "statistics",
        },
        TaskType.ANALYSIS: {
            "analyze", "audit", "diagnose", "evaluate", "inspect", "review",
        },
    }

    TOOL_TERMS = {
        "build", "create file", "delete", "deploy", "edit", "execute", "fetch",
        "filesystem", "install", "list directory", "list files", "open", "read file",
        "run", "search", "search web", "shell", "start server", "tool", "url",
        "write file",
    }
    MEMORY_TERMS = {
        "again", "context", "earlier", "history", "last time", "previous",
        "remember", "recall",
    }

    def classify(self, user_input: str) -> TaskClassification:
        if self.use_local_model:
            llm_result = self._classify_with_llm(user_input)
            if llm_result is not None:
                return llm_result
        return self._classify_with_keywords(user_input)

    # -- keyword backend ----------------------------------------------------

    def _classify_with_keywords(self, user_input: str) -> TaskClassification:
        text = self._normalize(user_input)
        scores = self._score_task_types(text)
        task_type, score = max(scores.items(), key=lambda item: item[1])

        if not text:
            task_type = TaskType.CONVERSATION
            score = 1

        confidence = self._confidence(score, len(text), scores)
        requires_tools = self._requires_tools(text, task_type)
        requires_memory = self._requires_memory(text, task_type)
        execution_requirements = self._execution_requirements(text, requires_tools)

        return TaskClassification(
            task_type=task_type,
            confidence=confidence,
            requires_tools=requires_tools,
            requires_memory=requires_memory,
            domain=self._detect_domain(text),
            urgency=self._detect_urgency(text),
            execution_requirements=execution_requirements,
            signals={
                "keyword_scores": {key.value: value for key, value in scores.items()},
                "input_words": len(text.split()),
                "backend": "keywords",
            },
        )

    # -- LLM backend --------------------------------------------------------

    LLM_SYSTEM_PROMPT = load_template("classifier")

    LLM_SCHEMA = {
        "type": "object",
        "properties": {
            "task_type": {
                "type": "string",
                "enum": [
                    "conversation", "coding", "research", "planning",
                    "creative", "reasoning", "automation", "math", "analysis",
                ],
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "requires_tools": {"type": "boolean"},
            "requires_memory": {"type": "boolean"},
            "domain": {"type": ["string", "null"]},
            "urgency": {"type": "string", "enum": ["normal", "elevated", "urgent"]},
            "execution_requirements": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "filesystem", "shell", "network", "runtime", "tool_layer",
                    ],
                },
            },
        },
        "required": [
            "task_type", "confidence", "requires_tools", "requires_memory",
        ],
    }

    def _classify_with_llm(self, user_input: str) -> TaskClassification | None:
        """Call the local model and validate its output. Returns ``None`` on
        any failure so the caller can fall back to keywords."""
        try:
            from core import ModelUnavailable, get_global_client
        except ImportError:
            return None
        try:
            client = get_global_client()
            prompt = (
                f"{self.LLM_SYSTEM_PROMPT}\n\nUser message:\n{user_input}"
            )
            raw = client.generate_structured(
                prompt=prompt,
                schema=self.LLM_SCHEMA,
                max_tokens=192,
                temperature=0.0,
            )
        except (ModelUnavailable, FileNotFoundError) as exc:
            logger.info("Local model unavailable, falling back to keywords: %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM classification failed, falling back: %s", exc)
            return None

        try:
            if raw.get("domain") in {"null", "", "none", "None"}:
                raw["domain"] = None
            classification = TaskClassification(
                task_type=raw["task_type"],
                confidence=float(raw.get("confidence", 0.75)),
                requires_tools=bool(raw.get("requires_tools", False)),
                requires_memory=bool(raw.get("requires_memory", False)),
                domain=raw.get("domain"),
                urgency=raw.get("urgency", "normal"),
                execution_requirements=list(raw.get("execution_requirements", []) or []),
                signals={"backend": "local_model", "raw_response": raw},
            )
        except (KeyError, ValidationError, ValueError, TypeError) as exc:
            logger.warning(
                "LLM classification produced invalid output, falling back: %s",
                exc,
            )
            return None
        return classification

    # -- helpers ------------------------------------------------------------

    def _score_task_types(self, text: str) -> dict[TaskType, int]:
        scores = {task_type: 0 for task_type in TaskType}
        for task_type, keywords in self.KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    scores[task_type] += 1

        if self._is_short_greeting(text):
            scores[TaskType.CONVERSATION] += 4
        if "test plan" in text or "implementation plan" in text:
            scores[TaskType.PLANNING] += 3
        if re.search(r"\d+\s*[\+\-\*/]\s*\d+", text):
            scores[TaskType.MATH] += 3
        if "operating system" in text or "distributed" in text:
            scores[TaskType.PLANNING] += 2
            scores[TaskType.ANALYSIS] += 1

        return scores

    def _confidence(
        self, winning_score: int, text_length: int, scores: dict[TaskType, int]
    ) -> float:
        if winning_score <= 0:
            return 0.5
        sorted_scores = sorted(scores.values(), reverse=True)
        margin = sorted_scores[0] - sorted_scores[1] if len(sorted_scores) > 1 else 1
        base = 0.58 + min(winning_score, 5) * 0.06 + min(margin, 4) * 0.04
        if text_length < 24:
            base += 0.05
        return round(min(base, 0.96), 2)

    def _requires_tools(self, text: str, task_type: TaskType) -> bool:
        if task_type in {TaskType.CODING, TaskType.AUTOMATION}:
            return True
        return any(term in text for term in self.TOOL_TERMS)

    def _requires_memory(self, text: str, task_type: TaskType) -> bool:
        if task_type in {TaskType.RESEARCH, TaskType.ANALYSIS, TaskType.PLANNING}:
            return True
        return any(term in text for term in self.MEMORY_TERMS)

    def _execution_requirements(self, text: str, requires_tools: bool) -> list[str]:
        requirements: list[str] = []
        if not requires_tools:
            return requirements
        if any(term in text for term in {"file", "filesystem", "write file", "edit"}):
            requirements.append("filesystem")
        if any(term in text for term in {"read file", "list directory", "list files"}):
            requirements.append("filesystem")
        if any(term in text for term in {"run", "execute", "shell", "install"}):
            requirements.append("shell")
        if any(term in text for term in {"search", "fetch", "url", "web"}):
            requirements.append("network")
        if any(term in text for term in {"deploy", "server", "start server"}):
            requirements.append("runtime")
        if not requirements:
            requirements.append("tool_layer")
        return requirements

    def _detect_domain(self, text: str) -> str | None:
        if any(term in text for term in {"api", "code", "python", "server"}):
            return "software"
        if any(term in text for term in {"architecture", "system", "distributed"}):
            return "systems"
        if any(term in text for term in {"money", "payment", "invoice"}):
            return "finance"
        if any(term in text for term in {"password", "token", "credential"}):
            return "security"
        return None

    def _detect_urgency(self, text: str) -> str:
        if any(term in text for term in {"urgent", "asap", "immediately"}):
            return "urgent"
        if any(term in text for term in {"soon", "today"}):
            return "elevated"
        return "normal"

    def _is_short_greeting(self, text: str) -> bool:
        compact = text.strip(" .!?")
        return compact in {"hi", "hello", "hey", "yo", "thanks", "thank you"}

    def _normalize(self, user_input: str) -> str:
        return " ".join(user_input.lower().strip().split())




class IntentClassification(BaseModel):
    intent: str
    confidence: float


class IntentClassifier:
    def __init__(self) -> None:
        self._classifier = TaskClassifier()

    def classify(self, user_input: str) -> IntentClassification:
        if not user_input.strip():
            raise ValueError("user_input is required")
        result = self._classifier.classify(user_input)
        return IntentClassification(intent=result.task_type.value, confidence=result.confidence)
