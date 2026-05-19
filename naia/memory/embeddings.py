"""Embeddings engine with support for real model embeddings and heuristic fallback."""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Embeddings engine with support for Anthropic embeddings and heuristic fallback."""

    def __init__(
        self,
        dimensions: int = 768,
        use_anthropic: bool = False,
        model: str = "claude-3-5-sonnet-20241022",
        api_key: str | None = None,
    ) -> None:
        """
        Initialize the embeddings engine.

        Args:
            dimensions: Embedding dimensions (768 for Claude embeddings)
            use_anthropic: Whether to use Anthropic's embeddings API
            model: Anthropic model to use
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.dimensions = dimensions
        self.use_anthropic = use_anthropic
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client: Any = None

        if use_anthropic:
            try:
                from anthropic import Anthropic
                if self.api_key:
                    self.client = Anthropic(api_key=self.api_key)
                    logger.info("Embeddings engine initialized with Anthropic")
                else:
                    logger.warning("ANTHROPIC_API_KEY not set, using heuristic embeddings")
                    self.use_anthropic = False
            except ImportError:
                logger.warning("Anthropic not installed, using heuristic embeddings")
                self.use_anthropic = False

    def embed(self, text: str) -> list[float]:
        """Generate embeddings for the given text."""
        if self.use_anthropic and self.client is not None:
            return self._embed_with_anthropic(text)
        return self._embed_with_heuristic(text)

    def _embed_with_anthropic(self, text: str) -> list[float]:
        """Generate embeddings using Anthropic's embeddings API.

        Anthropic's official client does not currently expose a dedicated
        embeddings endpoint, so this method is best-effort: it tries the
        ``embeddings.create`` shape and falls back to the heuristic embedder
        on any error. When/if Anthropic ships a stable embeddings API, this
        is the single point that needs updating.
        """
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            embedding = response.embedding[0].embedding
            if hasattr(embedding, "tolist"):
                return embedding.tolist()
            return list(embedding)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Anthropic embeddings failed, using heuristic: %s", exc)
            return self._embed_with_heuristic(text)

    def _embed_with_heuristic(self, text: str) -> list[float]:
        """Generate embeddings using hashing-based heuristic (original implementation)."""
        vector = [0.0 for _ in range(self.dimensions)]
        tokens = self._tokens(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [round(value / norm, 6) for value in vector]

    def similarity(self, first: list[float], second: list[float]) -> float:
        """Calculate cosine similarity between two embeddings."""
        if not first or not second or len(first) != len(second):
            return 0.0

        first_array = np.array(first)
        second_array = np.array(second)

        dot_product = np.dot(first_array, second_array)
        norm_first = np.linalg.norm(first_array)
        norm_second = np.linalg.norm(second_array)

        if norm_first == 0 or norm_second == 0:
            return 0.0

        return round(float(dot_product / (norm_first * norm_second)), 6)

    def _tokens(self, text: str) -> list[str]:
        """Tokenize text for heuristic embeddings."""
        return re.findall(r"[a-z0-9']+", text.lower())

    def is_using_real_embeddings(self) -> bool:
        """Check if using real model embeddings."""
        return self.use_anthropic and self.client is not None
