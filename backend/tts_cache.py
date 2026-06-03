"""A small in-memory cache for synthesized TTS audio of common phrases.

Conversations repeat short phrases constantly ("yes", "thank you", "where is
the bathroom", numbers, greetings). Re-synthesizing them every time wastes
latency and CPU. This module provides a thread-safe LRU cache keyed by the
(normalized text, language) pair, storing the raw audio bytes so a repeated
phrase can be replayed instantly without touching the TTS engine.

Only short phrases are cached (long, unique sentences rarely repeat and would
just evict useful entries), and the cache is size-bounded with LRU eviction.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from threading import RLock


class PhraseCache:
    def __init__(self, max_entries: int = 256, max_chars: int = 80):
        self.max_entries = max(0, int(max_entries))
        self.max_chars = max(1, int(max_chars))
        self._store: "OrderedDict[tuple[str, str], bytes]" = OrderedDict()
        self._lock = RLock()
        self.hits = 0
        self.misses = 0

    @property
    def enabled(self) -> bool:
        return self.max_entries > 0

    def _key(self, text: str, language: str | None) -> tuple[str, str] | None:
        normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
        if not normalized or len(normalized) > self.max_chars:
            return None
        return (normalized, (language or "").strip().lower())

    def get(self, text: str, language: str | None) -> bytes | None:
        if not self.enabled:
            return None
        key = self._key(text, language)
        if key is None:
            return None
        with self._lock:
            audio = self._store.get(key)
            if audio is None:
                self.misses += 1
                return None
            # Mark as most-recently used.
            self._store.move_to_end(key)
            self.hits += 1
            return audio

    def put(self, text: str, language: str | None, audio: bytes) -> None:
        if not self.enabled or not audio:
            return
        key = self._key(text, language)
        if key is None:
            return
        with self._lock:
            self._store[key] = audio
            self._store.move_to_end(key)
            while len(self._store) > self.max_entries:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self.hits = 0
            self.misses = 0

    def stats(self) -> dict:
        with self._lock:
            total = self.hits + self.misses
            return {
                "entries": len(self._store),
                "max_entries": self.max_entries,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / total, 4) if total else 0.0,
            }


def _build_default_cache() -> PhraseCache:
    try:
        from backend.config import get_tts_phrase_cache_size

        size = get_tts_phrase_cache_size()
    except Exception:  # noqa: BLE001 - never let config issues break TTS
        size = 256
    return PhraseCache(max_entries=size)


phrase_cache = _build_default_cache()
