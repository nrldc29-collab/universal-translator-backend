import re
from collections import Counter
from threading import RLock
from time import time


_STOP_WORDS = {
    "the", "and", "for", "that", "this", "with", "you", "are", "was", "were",
    "have", "from", "your", "about", "what", "when", "where", "there", "here",
}


def _topic_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]{3,}", (text or "").lower())
    return [token for token in tokens if token not in _STOP_WORDS][:8]


class ConversationMemory:
    def __init__(self, limit: int = 40):
        self.limit = limit
        self.history = []
        self._lock = RLock()

    def add(self, speaker, original, translated, metadata=None):
        original_text = str(original or "").strip()
        translated_text = str(translated or "").strip()
        if not original_text and not translated_text:
            return
        entry = {
            "speaker": speaker,
            "original": original_text,
            "translated": translated_text,
            "topics": _topic_tokens(f"{original_text} {translated_text}"),
            "created_at": time(),
        }
        if metadata:
            entry["metadata"] = metadata
        with self._lock:
            self.history.append(entry)
            self.history = self.history[-self.limit:]

    def get_context(self, limit: int | None = None):
        with self._lock:
            items = list(self.history)
        if limit is not None:
            return items[-limit:]
        return items

    def recent_topics(self, limit: int = 6) -> list[str]:
        with self._lock:
            counter = Counter(topic for item in self.history for topic in item.get("topics", []))
        return [topic for topic, _ in counter.most_common(limit)]

    def context_match_score(self, text: str) -> float:
        tokens = set(_topic_tokens(text))
        if not tokens:
            return 0.55
        topics = set(self.recent_topics(12))
        if not topics:
            return 0.6
        overlap = len(tokens & topics) / max(1, len(tokens))
        return min(1.0, 0.55 + overlap * 0.4)
