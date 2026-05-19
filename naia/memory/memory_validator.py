"""Validation for memory corruption, contradictions, and duplicates."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from memory.embeddings import EmbeddingEngine
from memory.memory_policy import MemoryStatus, MemoryWriteCandidate
from memory.memory_store import MemoryRecord


class MemoryValidationResult(BaseModel):
    valid: bool
    reason: str = ""
    action: str = "allow"
    duplicate_of: str | None = None
    conflicts_with: list[str] = Field(default_factory=list)


class MemoryValidator:
    NEGATORS = {"not", "no", "never", "cannot", "can't", "cant", "won't", "wont"}

    def __init__(self, embeddings: EmbeddingEngine | None = None) -> None:
        self.embeddings = embeddings or EmbeddingEngine()

    def validate(
        self,
        candidate: MemoryWriteCandidate,
        existing_records: list[MemoryRecord],
    ) -> MemoryValidationResult:
        text = candidate.content.strip()
        if not text:
            return MemoryValidationResult(
                valid=False, reason="empty content", action="reject"
            )

        normalized = self._normalize(text)
        candidate_vector = self.embeddings.embed(text)
        for record in existing_records:
            if record.status != MemoryStatus.ACTIVE:
                continue
            if self._normalize(record.content) == normalized:
                return MemoryValidationResult(
                    valid=False,
                    reason="duplicate memory",
                    action="reject",
                    duplicate_of=record.memory_id,
                )
            if self._contradicts(candidate.content, record.content):
                return MemoryValidationResult(
                    valid=False,
                    reason="conflicts with existing memory",
                    action="quarantine",
                    conflicts_with=[record.memory_id],
                )
            similarity = self.embeddings.similarity(candidate_vector, record.vector)
            if similarity >= 0.92:
                return MemoryValidationResult(
                    valid=False,
                    reason="near-duplicate memory",
                    action="reject",
                    duplicate_of=record.memory_id,
                )

        return MemoryValidationResult(valid=True, reason="memory valid")

    def _contradicts(self, first: str, second: str) -> bool:
        first_signature = self._signature(first)
        second_signature = self._signature(second)
        if not first_signature or first_signature != second_signature:
            return False
        return self._polarity(first) != self._polarity(second)

    def _signature(self, text: str) -> str:
        tokens = [
            token
            for token in re.findall(r"[a-z0-9']+", text.lower())
            if token not in self.NEGATORS
            and token not in {"i", "the", "a", "an", "is", "are", "be"}
        ]
        return " ".join(tokens[:8])

    def _polarity(self, text: str) -> str:
        tokens = set(re.findall(r"[a-z0-9']+", text.lower()))
        return "negative" if tokens & self.NEGATORS else "positive"

    def _normalize(self, text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
