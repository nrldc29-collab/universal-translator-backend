"""RAG-style retrieval over episodic and semantic memory."""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, Field

from memory.embeddings import EmbeddingEngine
from memory.memory_policy import MemoryType
from memory.memory_store import MemorySearchResult, MemoryStore
from memory.retriever import MemoryRetriever, RetrievalRequest

logger = logging.getLogger(__name__)


class RAGRetrievalRequest(BaseModel):
    """Request for RAG-style retrieval."""

    query: str
    context: dict[str, Any] = Field(default_factory=dict)
    top_k: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.5, ge=0.0, le=1.0)
    include_episodic: bool = True
    include_semantic: bool = True
    include_procedural: bool = False


class RAGRetrievalResult(BaseModel):
    """Result from RAG-style retrieval."""

    query: str
    episodic_memories: list[MemorySearchResult] = Field(default_factory=list)
    semantic_memories: list[MemorySearchResult] = Field(default_factory=list)
    procedural_memories: list[MemorySearchResult] = Field(default_factory=list)
    combined_context: str = ""
    retrieval_metadata: dict[str, Any] = Field(default_factory=dict)


class RAGRetriever:
    """RAG-style retrieval over episodic and semantic memory using embeddings and reranking."""

    def __init__(
        self,
        store: MemoryStore,
        embeddings: EmbeddingEngine | None = None,
        use_claude_rerank: bool = False,
        claude_model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        """
        Initialize the RAG retriever.

        Args:
            store: Memory store to retrieve from
            embeddings: Embeddings engine for similarity search
            use_claude_rerank: Whether to use Claude for reranking results
            claude_model: Claude model for reranking
        """
        self.store = store
        self.embeddings = embeddings or EmbeddingEngine(use_anthropic=True)
        self.use_claude_rerank = use_claude_rerank
        self.claude_model = claude_model
        self.client: Anthropic | None = None

        if use_claude_rerank:
            try:
                import os
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if api_key:
                    self.client = Anthropic(api_key=api_key)
                    logger.info("RAG retriever initialized with Claude reranking")
                else:
                    logger.warning("ANTHROPIC_API_KEY not set, Claude reranking disabled")
                    self.use_claude_rerank = False
            except ImportError:
                logger.warning("Anthropic not installed, Claude reranking disabled")
                self.use_claude_rerank = False

    def retrieve(self, request: RAGRetrievalRequest) -> RAGRetrievalResult:
        """
        Perform RAG-style retrieval over episodic and semantic memory.

        Args:
            request: RAG retrieval request

        Returns:
            RAG retrieval result with combined context
        """
        # Determine which memory types to search
        memory_types = []
        if request.include_episodic:
            memory_types.append(MemoryType.EPISODIC)
        if request.include_semantic:
            memory_types.append(MemoryType.SEMANTIC)
        if request.include_procedural:
            memory_types.append(MemoryType.PROCEDURAL)

        # Use the base retriever for initial similarity search
        base_retriever = MemoryRetriever(store=self.store, embeddings=self.embeddings)
        base_request = RetrievalRequest(
            query=request.query,
            memory_types=memory_types,
            min_confidence=0.0,  # Let similarity be the primary filter
            limit=request.top_k * 2,  # Get more candidates for reranking
            include_recent=True,
        )
        base_result = base_retriever.retrieve(base_request)

        # Filter by similarity threshold
        filtered = [
            result
            for result in base_result.memories
            if result.similarity >= request.min_similarity
        ]

        # Separate by memory type
        episodic = [r for r in filtered if r.record.memory_type == MemoryType.EPISODIC]
        semantic = [r for r in filtered if r.record.memory_type == MemoryType.SEMANTIC]
        procedural = [r for r in filtered if r.record.memory_type == MemoryType.PROCEDURAL]

        # Rerank with Claude if enabled
        if self.use_claude_rerank and self.client is not None:
            episodic = self._rerank_with_claude(request.query, episodic)
            semantic = self._rerank_with_claude(request.query, semantic)
            procedural = self._rerank_with_claude(request.query, procedural)

        # Take top_k from each type
        k_per_type = max(1, request.top_k // len(memory_types)) if memory_types else request.top_k
        episodic = episodic[:k_per_type]
        semantic = semantic[:k_per_type]
        procedural = procedural[:k_per_type]

        # Combine into context
        combined_context = self._build_combined_context(
            request.query, episodic, semantic, procedural
        )

        return RAGRetrievalResult(
            query=request.query,
            episodic_memories=episodic,
            semantic_memories=semantic,
            procedural_memories=procedural,
            combined_context=combined_context,
            retrieval_metadata={
                "total_candidates": len(base_result.memories),
                "filtered_count": len(filtered),
                "episodic_count": len(episodic),
                "semantic_count": len(semantic),
                "procedural_count": len(procedural),
                "reranking_enabled": self.use_claude_rerank,
            },
        )

    def _rerank_with_claude(
        self, query: str, results: list[MemorySearchResult]
    ) -> list[MemorySearchResult]:
        """Rerank results using Claude for better relevance."""
        if not results:
            return results

        try:
            # Build prompt for reranking
            results_text = "\n\n".join([
                f"{i+1}. {result.record.content}"
                for i, result in enumerate(results)
            ])

            system_prompt = """You are a relevance ranker. Given a query and a list of memory items, rank them by relevance to the query.

Return your ranking as a JSON list of indices in order of most relevant to least relevant.
For example: [3, 1, 4, 2]"""

            user_prompt = f"""Query: {query}

Memory items:
{results_text}

Rank these memory items by relevance to the query. Return as JSON list of indices."""

            response = self.client.messages.create(
                model=self.claude_model,
                max_tokens=256,
                temperature=0.2,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            content = response.content[0].text

            # Parse ranking
            import json
            import re

            json_match = re.search(r'\[[\d,\s]+\]', content)
            if json_match:
                ranking = json.loads(json_match.group())
                # Reorder results based on ranking
                ranked = [results[i - 1] for i in ranking if 1 <= i <= len(results)]
                return ranked
        except Exception as exc:
            logger.warning("Claude reranking failed, using original order: %s", exc)

        return results

    def _build_combined_context(
        self,
        query: str,
        episodic: list[MemorySearchResult],
        semantic: list[MemorySearchResult],
        procedural: list[MemorySearchResult],
    ) -> str:
        """Build combined context from retrieved memories."""
        context_parts = [f"Query: {query}\n"]

        if episodic:
            context_parts.append("## Episodic Memory")
            for result in episodic:
                context_parts.append(
                    f"- [similarity={result.similarity:.2f}] {result.record.content}"
                )

        if semantic:
            context_parts.append("\n## Semantic Memory")
            for result in semantic:
                context_parts.append(
                    f"- [similarity={result.similarity:.2f}] {result.record.content}"
                )

        if procedural:
            context_parts.append("\n## Procedural Memory")
            for result in procedural:
                context_parts.append(
                    f"- [similarity={result.similarity:.2f}] {result.record.content}"
                )

        return "\n".join(context_parts)

    def is_available(self) -> bool:
        """Check if RAG retriever is available."""
        return self.store is not None
