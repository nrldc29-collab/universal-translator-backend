"""Memory retrieval, ranking, and filtering."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from memory.embeddings import EmbeddingEngine
from memory.memory_policy import MemoryType
from memory.memory_store import MemoryRecord, MemorySearchResult, MemoryStore


class RetrievalRequest(BaseModel):
    query: str
    memory_types: list[MemoryType] | None = None
    min_confidence: float = Field(default=0.35, ge=0.0, le=1.0)
    limit: int = Field(default=5, ge=1, le=25)
    include_recent: bool = True


class RetrievalResult(BaseModel):
    memories: list[MemorySearchResult]
    query: str
    injected_context: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryRetriever:
    def __init__(
        self,
        store: MemoryStore,
        embeddings: EmbeddingEngine | None = None,
    ) -> None:
        self.store = store
        self.embeddings = embeddings or EmbeddingEngine(use_anthropic=True)

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        query_vector = self.embeddings.embed(request.query)
        query_tokens = self._tokens(request.query)
        records = self.store.active_records()
        if request.memory_types is not None:
            allowed_types = set(request.memory_types)
            records = [record for record in records if record.memory_type in allowed_types]

        ranked: list[MemorySearchResult] = []
        now = datetime.now(timezone.utc)
        for record in records:
            if record.confidence < request.min_confidence:
                continue
            similarity = self.embeddings.similarity(query_vector, record.vector)
            recency = self._recency_score(record, now) if request.include_recent else 0
            overlap = self._token_overlap(query_tokens, record.content)
            type_boost = self._type_boost(record.memory_type)
            score = (
                similarity * 0.42
                + overlap * 0.22
                + record.confidence * 0.2
                + record.importance * 0.1
                + recency * 0.03
                + type_boost
            )
            if "prefer" in query_tokens and "prefer" in self._tokens(record.content):
                score += 0.12
            if score <= 0:
                continue
            ranked.append(
                MemorySearchResult(
                    record=record,
                    similarity=similarity,
                    score=round(score, 4),
                )
            )

        ranked.sort(key=lambda item: item.score, reverse=True)
        selected = ranked[: request.limit]
        self.store.mark_accessed([item.record.memory_id for item in selected])
        return RetrievalResult(
            memories=selected,
            query=request.query,
            injected_context=self._context_from(selected),
            metadata={"candidate_count": len(records), "selected_count": len(selected)},
        )

    def _tokens(self, text: str) -> set[str]:
        tokens = set(re.findall(r"[a-z0-9']+", text.lower()))
        if "preference" in tokens:
            tokens.add("prefer")
        return tokens

    def _token_overlap(self, query_tokens: set[str], content: str) -> float:
        if not query_tokens:
            return 0.0
        content_tokens = self._tokens(content)
        return len(query_tokens & content_tokens) / len(query_tokens)

    def _type_boost(self, memory_type: MemoryType) -> float:
        if memory_type == MemoryType.SEMANTIC:
            return 0.14
        if memory_type == MemoryType.PROCEDURAL:
            return 0.08
        return 0.0

    def _recency_score(self, record: MemoryRecord, now: datetime) -> float:
        age_days = max((now - record.created_at).total_seconds() / 86_400, 0)
        if age_days <= 1:
            return 1.0
        if age_days <= 7:
            return 0.7
        if age_days <= 30:
            return 0.35
        return 0.1

    def _context_from(self, results: list[MemorySearchResult]) -> str:
        lines: list[str] = []
        for result in results:
            record = result.record
            lines.append(
                f"[{record.memory_type.value}; confidence={record.confidence:.2f}] "
                f"{record.content}"
            )
        return "\n".join(lines)
