"""Main orchestrator for governed memory operations."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from memory.embeddings import EmbeddingEngine
from memory.episodic import EpisodicMemory
from memory.indexer import MemoryIndexer
from memory.memory_policy import (
    MemoryPolicyEngine,
    MemoryStatus,
    MemoryType,
    MemoryWriteCandidate,
    PolicyAction,
)
from memory.memory_store import MemoryRecord, MemoryStore
from memory.memory_validator import MemoryValidationResult, MemoryValidator
from memory.procedural import ProceduralMemory
from memory.retriever import MemoryRetriever, RetrievalRequest, RetrievalResult
from memory.semantic import SemanticMemory

logger = logging.getLogger(__name__)


class MemoryWriteResult(BaseModel):
    stored: bool
    record: MemoryRecord | None = None
    validation: MemoryValidationResult | None = None
    policy_action: str
    status: str
    reason: str = ""


class MemoryDecayResult(BaseModel):
    decayed: int = 0
    expired: int = 0


class MemoryForgetResult(BaseModel):
    forgotten: bool
    record: MemoryRecord | None = None
    status: str
    reason: str


class MemoryEngine:
    def __init__(
        self,
        *,
        db_path: str | Path | None = None,
        store: MemoryStore | None = None,
        embeddings: EmbeddingEngine | None = None,
        policy: MemoryPolicyEngine | None = None,
        validator: MemoryValidator | None = None,
        indexer: MemoryIndexer | None = None,
    ) -> None:
        self.embeddings = embeddings or EmbeddingEngine()
        self.store = store or MemoryStore(db_path=db_path)
        self.policy = policy or MemoryPolicyEngine()
        self.validator = validator or MemoryValidator(self.embeddings)
        self.indexer = indexer or MemoryIndexer()
        self.retriever = MemoryRetriever(self.store, self.embeddings)
        self._lock = threading.Lock()
        self._write_count = 0
        self._write_errors = 0
        self._retrieve_count = 0
        self._retrieve_errors = 0
        self._decay_count = 0
        self._forget_count = 0
        self._forget_errors = 0
        logger.info(f"MemoryEngine initialized with db_path={self.store.db_path}")

    def write(self, candidate: MemoryWriteCandidate) -> MemoryWriteResult:
        start_time = time.time()
        try:
            with self._lock:
                result = self._write_unlocked(candidate)
            self._write_count += 1
            logger.debug(f"Memory write completed: stored={result.stored}, type={candidate.memory_type}")
            return result
        except Exception as e:
            self._write_errors += 1
            logger.error(f"Memory write failed: {e}", exc_info=True)
            return MemoryWriteResult(
                stored=False,
                policy_action="error",
                status="error",
                reason=f"Write failed: {str(e)[:100]}",
            )
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"Memory write took {duration_ms:.2f}ms")

    def _write_unlocked(self, candidate: MemoryWriteCandidate) -> MemoryWriteResult:
        policy_decision = self.policy.decide_write(candidate)
        if policy_decision.action == PolicyAction.REJECT:
            return MemoryWriteResult(
                stored=False,
                policy_action=policy_decision.action.value,
                status=policy_decision.status.value,
                reason=policy_decision.reason,
            )

        existing = self.store.active_records()
        validation = self.validator.validate(candidate, existing)
        status = policy_decision.status
        reason = policy_decision.reason or validation.reason

        if validation.action == "reject":
            return MemoryWriteResult(
                stored=False,
                validation=validation,
                policy_action=PolicyAction.REJECT.value,
                status=MemoryStatus.REJECTED.value,
                reason=validation.reason,
            )
        if validation.action == "quarantine":
            status = MemoryStatus.QUARANTINED
            reason = validation.reason

        vector = self.embeddings.embed(f"{candidate.content} {candidate.context}")
        topic = self.indexer.topic_for(candidate)
        record = self.store.write(
            candidate,
            vector=vector,
            status=status,
            sensitivity=policy_decision.sensitivity,
            topic=topic,
            decay_rate=policy_decision.decay_rate,
        )
        return MemoryWriteResult(
            stored=True,
            record=record,
            validation=validation,
            policy_action=policy_decision.action.value,
            status=status.value,
            reason=reason,
        )

    def write_episodic(self, memory: EpisodicMemory) -> MemoryWriteResult:
        return self.write(
            MemoryWriteCandidate(
                memory_type=MemoryType.EPISODIC,
                content=f"{memory.event}: {memory.context[:500]}",
                context=memory.context,
                confidence=memory.confidence,
                importance=memory.importance,
                source="runtime_episode",
                session_id=memory.session_id,
                metadata=memory.metadata | {"timestamp": memory.timestamp.isoformat()},
            )
        )

    def write_semantic(self, memory: SemanticMemory) -> MemoryWriteResult:
        return self.write(
            MemoryWriteCandidate(
                memory_type=MemoryType.SEMANTIC,
                content=memory.fact,
                context=f"source={memory.source}",
                confidence=memory.confidence,
                importance=0.75,
                source=memory.source,
                metadata=memory.metadata
                | {
                    "last_verified": (
                        memory.last_verified.isoformat()
                        if memory.last_verified
                        else None
                    ),
                    "requires_approval": memory.requires_approval,
                },
            )
        )

    def write_procedural(self, memory: ProceduralMemory) -> MemoryWriteResult:
        return self.write(
            MemoryWriteCandidate(
                memory_type=MemoryType.PROCEDURAL,
                content=f"{memory.procedure}: {'; '.join(memory.steps)}",
                context="procedure",
                confidence=memory.confidence,
                importance=0.7,
                source=memory.source,
                metadata=memory.metadata
                | {
                    "procedure": memory.procedure,
                    "steps": memory.steps,
                    "success_count": memory.success_count,
                },
            )
        )

    def retrieve(
        self,
        query: str,
        *,
        memory_types: list[MemoryType] | None = None,
        min_confidence: float = 0.35,
        limit: int = 5,
    ) -> RetrievalResult:
        start_time = time.time()
        try:
            result = self.retriever.retrieve(
                RetrievalRequest(
                    query=query,
                    memory_types=memory_types,
                    min_confidence=min_confidence,
                    limit=limit,
                )
            )
            self._retrieve_count += 1
            logger.debug(f"Memory retrieve completed: found={len(result.results)} results")
            return result
        except Exception as e:
            self._retrieve_errors += 1
            logger.error(f"Memory retrieve failed: {e}", exc_info=True)
            return RetrievalResult(results=[], query=query, error=str(e))
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"Memory retrieve took {duration_ms:.2f}ms")

    def decay(self) -> MemoryDecayResult:
        start_time = time.time()
        try:
            with self._lock:
                records = self.store.active_records()
            now = datetime.now(timezone.utc)
            decayed = 0
            expired = 0
            for record in records:
                age_days = max((now - record.updated_at).total_seconds() / 86_400, 0)
                if age_days <= 0:
                    continue
                new_confidence = max(
                    0.0,
                    record.confidence - (record.decay_rate * age_days),
                )
                if new_confidence == record.confidence:
                    continue
                status = MemoryStatus.EXPIRED if new_confidence < 0.15 else None
                if status == MemoryStatus.EXPIRED:
                    expired += 1
                decayed += 1
                self.store.update_confidence(
                    record.memory_id,
                    round(new_confidence, 4),
                    status=status,
                )
            self._decay_count += 1
            logger.info(f"Memory decay completed: decayed={decayed}, expired={expired}")
            return MemoryDecayResult(decayed=decayed, expired=expired)
        except Exception as e:
            logger.error(f"Memory decay failed: {e}", exc_info=True)
            return MemoryDecayResult(decayed=0, expired=0)
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"Memory decay took {duration_ms:.2f}ms")

    def forget(self, memory_id: str, *, reason: str) -> MemoryForgetResult:
        start_time = time.time()
        try:
            with self._lock:
                decision = self.policy.can_soft_delete(reason=reason)
                if decision.action != PolicyAction.ALLOW:
                    return MemoryForgetResult(
                        forgotten=False,
                        status=decision.status.value,
                        reason=decision.reason,
                    )
                record = self.store.update_status(
                    memory_id,
                    MemoryStatus.EXPIRED,
                    metadata_update={
                        "forget_reason": reason,
                        "forgotten_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            self._forget_count += 1
            logger.info(f"Memory forget completed: memory_id={memory_id}, forgotten={record is not None}")
            return MemoryForgetResult(
                forgotten=record is not None,
                record=record,
                status=record.status.value if record else "missing",
                reason=decision.reason if record else "memory not found",
            )
        except Exception as e:
            self._forget_errors += 1
            logger.error(f"Memory forget failed: {e}", exc_info=True)
            return MemoryForgetResult(
                forgotten=False,
                status="error",
                reason=f"Forget failed: {str(e)[:100]}",
            )
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"Memory forget took {duration_ms:.2f}ms")

    def extract_semantic_candidate(
        self, text: str, *, session_id: str | None = None
    ) -> MemoryWriteCandidate | None:
        lowered = text.lower().strip()
        prefixes = [
            "remember that ",
            "remember: ",
            "my preference is ",
            "i prefer ",
        ]
        for prefix in prefixes:
            if lowered.startswith(prefix):
                fact = text[len(prefix) :].strip(" .")
                if not fact:
                    return None
                if prefix == "i prefer ":
                    fact = f"User prefers {fact}"
                elif prefix == "my preference is ":
                    fact = f"User preference: {fact}"
                return MemoryWriteCandidate(
                    memory_type=MemoryType.SEMANTIC,
                    content=fact,
                    context="explicit user memory request",
                    confidence=0.82,
                    importance=0.75,
                    source="user_statement",
                    session_id=session_id,
                    metadata={"extracted_from": text},
                )
        return None

    def status(self) -> dict[str, Any]:
        """Get memory engine statistics."""
        try:
            return {
                "db_path": str(self.store.db_path),
                "by_status": self.store.count_by_status(),
                "by_type": self.store.count_by_type(),
                "write_count": self._write_count,
                "write_errors": self._write_errors,
                "retrieve_count": self._retrieve_count,
                "retrieve_errors": self._retrieve_errors,
                "decay_count": self._decay_count,
                "forget_count": self._forget_count,
                "forget_errors": self._forget_errors,
                "write_error_rate": self._write_errors / self._write_count if self._write_count > 0 else 0,
                "retrieve_error_rate": self._retrieve_errors / self._retrieve_count if self._retrieve_count > 0 else 0,
                "forget_error_rate": self._forget_errors / self._forget_count if self._forget_count > 0 else 0,
            }
        except Exception as e:
            logger.error(f"Failed to get memory status: {e}", exc_info=True)
            return {
                "db_path": str(self.store.db_path),
                "error": str(e),
                "write_count": self._write_count,
                "write_errors": self._write_errors,
            }
