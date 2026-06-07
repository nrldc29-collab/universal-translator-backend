"""
Predictive Translation Cache

This module implements intelligent caching for translation results:
- Phrase-level caching
- Context-aware predictions
- LRU eviction with priority
- Pre-fetching based on conversation patterns
- Cache warming for common phrases

Usage:
    from backend.predictive_cache import PredictiveCache
    cache = PredictiveCache(max_size=1000)
    cached = cache.get_translation(text, source_lang, target_lang)
"""

import hashlib
import time
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict
from threading import RLock
import re


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    translation: str
    timestamp: float
    access_count: int
    context: Dict = field(default_factory=dict)
    priority: int = 1  # Higher = more important


class PredictiveCache:
    """Predictive translation cache with context awareness."""
    
    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 3600,
        enable_predictions: bool = True,
    ):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.enable_predictions = enable_predictions
        
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.pattern_history: List[str] = []
        # Single shared instance is read by /metrics while translation writes to
        # it; RLock (reentrant) lets nested calls like set->_evict stay safe.
        self._lock = RLock()
        
        # Common phrases for cache warming
        self.common_phrases = {
            "en": [
                "hello", "thank you", "please", "yes", "no",
                "how are you", "good morning", "goodbye", "excuse me",
                "i don't understand", "can you help me", "where is",
            ],
            "es": [
                "hola", "gracias", "por favor", "sí", "no",
                "cómo estás", "buenos días", "adiós", "disculpe",
                "no entiendo", "puede ayudarme", "dónde está",
            ],
            "ht": [
                "bonjou", "mèsi", "tanpri", "wi", "non",
                "koman ou ye", "bon maten", "na wè pita", "eskize m",
                "m pa konprann", "ou ka ede m", "kote ye",
            ],
        }
    
    def _make_key(self, text: str, source_lang: str, target_lang: str) -> str:
        """Create cache key."""
        normalized = text.lower().strip()
        key = f"{source_lang}:{target_lang}:{normalized}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def get_translation(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        context: Dict = None,
    ) -> Optional[str]:
        """Get cached translation if available."""
        key = self._make_key(text, source_lang, target_lang)

        with self._lock:
            if key not in self.cache:
                return None

            entry = self.cache[key]

            # Check TTL
            if time.time() - entry.timestamp > self.ttl_seconds:
                del self.cache[key]
                return None

            # Update access
            entry.access_count += 1
            entry.context.update(context or {})

            # Move to end (LRU)
            self.cache.move_to_end(key)

            # Track pattern
            self._track_pattern(text)

            return entry.translation
    
    def set_translation(
        self,
        text: str,
        translation: str,
        source_lang: str,
        target_lang: str,
        context: Dict = None,
        priority: int = 1,
    ):
        """Cache translation result."""
        key = self._make_key(text, source_lang, target_lang)
        
        entry = CacheEntry(
            translation=translation,
            timestamp=time.time(),
            access_count=1,
            context=context or {},
            priority=priority,
        )

        with self._lock:
            # Evict if necessary
            if len(self.cache) >= self.max_size:
                self._evict()

            self.cache[key] = entry
            self.cache.move_to_end(key)
    
    def _evict(self):
        """Evict least important entry."""
        # First try to evict old entries
        now = time.time()
        for key in list(self.cache.keys()):
            entry = self.cache[key]
            if now - entry.timestamp > self.ttl_seconds:
                del self.cache[key]
                if len(self.cache) < self.max_size:
                    return
        
        # If still full, evict low priority
        if len(self.cache) >= self.max_size:
            # Find lowest priority
            min_priority = min(e.priority for e in self.cache.values())
            for key in list(self.cache.keys()):
                if self.cache[key].priority == min_priority:
                    del self.cache[key]
                    if len(self.cache) < self.max_size:
                        return
        
        # Last resort: evict oldest (LRU)
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
    
    def _track_pattern(self, text: str):
        """Track usage patterns for predictions."""
        with self._lock:
            self.pattern_history.append(text.lower())
            if len(self.pattern_history) > 1000:
                self.pattern_history.pop(0)
    
    def predict_next(self, context: List[str], source_lang: str) -> List[str]:
        """Predict likely next phrases based on context."""
        if not self.enable_predictions:
            return []
        
        # Simple n-gram prediction
        predictions = []

        if len(context) >= 2:
            # Look for patterns ending with last 2 words
            last_two = " ".join(context[-2:])
            with self._lock:
                history = list(self.pattern_history)
            for i in range(len(history) - 2):
                if history[i] == last_two:
                    next_phrase = history[i + 2]
                    if next_phrase not in predictions:
                        predictions.append(next_phrase)
                        if len(predictions) >= 5:
                            break

        return predictions
    
    def warm_cache(self, source_lang: str, target_lang: str, translator_func):
        """Warm cache with common phrases."""
        if source_lang not in self.common_phrases:
            return
        
        phrases = self.common_phrases[source_lang]
        
        for phrase in phrases:
            try:
                translation = translator_func(phrase, source_lang, target_lang)
                if translation:
                    self.set_translation(
                        phrase,
                        translation,
                        source_lang,
                        target_lang,
                        priority=2,  # Higher priority for common phrases
                    )
            except Exception:
                continue
    
    def get_statistics(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            if not self.cache:
                return {
                    "size": 0,
                    "hit_rate": 0.0,
                    "total_accesses": 0,
                    "total_hits": 0,
                }

            total_accesses = sum(e.access_count for e in self.cache.values())
            total_hits = total_accesses - len(self.cache)  # Approximate

            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hit_rate": total_hits / max(1, total_accesses),
                "total_accesses": total_accesses,
                "total_hits": total_hits,
                "pattern_history_size": len(self.pattern_history),
            }

    def clear(self):
        """Clear cache."""
        with self._lock:
            self.cache.clear()
            self.pattern_history = []
