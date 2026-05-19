"""Memory indexing for topics and lightweight retrieval organization."""

from __future__ import annotations

import re

from memory.memory_policy import MemoryWriteCandidate


class MemoryIndexer:
    STOPWORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "be",
        "for",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "to",
        "with",
    }

    def topic_for(self, candidate: MemoryWriteCandidate) -> str:
        tokens = [
            token
            for token in re.findall(r"[a-z0-9']+", candidate.content.lower())
            if token not in self.STOPWORDS
        ]
        if not tokens:
            return "general"
        topic_counts: dict[str, int] = {}
        for token in tokens:
            topic_counts[token] = topic_counts.get(token, 0) + 1
        return max(topic_counts.items(), key=lambda item: item[1])[0]

    def extract_topics(self, text: str, *, limit: int = 5) -> list[str]:
        tokens = [
            token
            for token in re.findall(r"[a-z0-9']+", text.lower())
            if token not in self.STOPWORDS and len(token) > 2
        ]
        seen: set[str] = set()
        topics: list[str] = []
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            topics.append(token)
            if len(topics) >= limit:
                break
        return topics or ["general"]
