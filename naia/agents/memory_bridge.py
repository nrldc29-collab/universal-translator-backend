"""Governed bridge between agents and memory."""

from __future__ import annotations

from memory.episodic import EpisodicMemory
from memory.memory_engine import MemoryEngine, MemoryWriteResult
from memory.retriever import RetrievalResult


class AgentMemoryBridge:
    def __init__(self, memory_engine: MemoryEngine) -> None:
        self.memory_engine = memory_engine

    def retrieve_context(self, query: str, *, limit: int = 3) -> RetrievalResult:
        return self.memory_engine.retrieve(query, limit=limit)

    def record_agent_event(
        self,
        *,
        agent_id: str,
        session_id: str | None,
        event: str,
        context: str,
        importance: float = 0.6,
        confidence: float = 0.75,
    ) -> MemoryWriteResult:
        return self.memory_engine.write_episodic(
            EpisodicMemory(
                session_id=session_id or agent_id,
                event=event,
                context=context,
                importance=importance,
                confidence=confidence,
                metadata={"agent_id": agent_id},
            )
        )
