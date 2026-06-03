"""Tests for backend.tts_cache.PhraseCache."""

from backend.tts_cache import PhraseCache


def test_put_and_get_round_trip():
    cache = PhraseCache(max_entries=8)
    cache.put("Thank you", "es", b"audio-bytes")
    assert cache.get("thank you", "es") == b"audio-bytes"


def test_key_is_normalized():
    cache = PhraseCache(max_entries=8)
    cache.put("  Hello   World ", "en", b"hi")
    # Whitespace-collapsed and case-insensitive lookups hit the same entry.
    assert cache.get("hello world", "en") == b"hi"


def test_language_is_part_of_key():
    cache = PhraseCache(max_entries=8)
    cache.put("hola", "es", b"es-audio")
    assert cache.get("hola", "fr") is None
    assert cache.get("hola", "es") == b"es-audio"


def test_miss_returns_none():
    cache = PhraseCache(max_entries=8)
    assert cache.get("nothing", "en") is None


def test_long_phrases_are_not_cached():
    cache = PhraseCache(max_entries=8, max_chars=10)
    cache.put("this phrase is far too long to cache", "en", b"x")
    assert cache.get("this phrase is far too long to cache", "en") is None


def test_lru_eviction():
    cache = PhraseCache(max_entries=2)
    cache.put("a", "en", b"1")
    cache.put("b", "en", b"2")
    # Touch "a" so "b" becomes the least-recently used.
    assert cache.get("a", "en") == b"1"
    cache.put("c", "en", b"3")
    assert cache.get("b", "en") is None
    assert cache.get("a", "en") == b"1"
    assert cache.get("c", "en") == b"3"


def test_disabled_when_size_zero():
    cache = PhraseCache(max_entries=0)
    assert cache.enabled is False
    cache.put("hi", "en", b"x")
    assert cache.get("hi", "en") is None


def test_empty_audio_not_stored():
    cache = PhraseCache(max_entries=8)
    cache.put("hi", "en", b"")
    assert cache.get("hi", "en") is None


def test_stats_track_hits_and_misses():
    cache = PhraseCache(max_entries=8)
    cache.put("hi", "en", b"x")
    cache.get("hi", "en")
    cache.get("missing", "en")
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["entries"] == 1
    assert stats["hit_rate"] == 0.5
