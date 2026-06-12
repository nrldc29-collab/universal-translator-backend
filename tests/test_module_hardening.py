"""Defensive guards on interconnected backend modules (Phase 3)."""

from backend.latency import StageMetrics
from backend.memory import ConversationMemory
from backend.smart_buffer import Priority, SmartBuffer
from backend.streaming import _sanitize_language_code, _sanitize_session_id
from backend.streaming_helpers import sanitize_text_for_tts


def test_conversation_memory_clamps_limit():
    mem = ConversationMemory(limit=9999)
    assert mem.limit == 500
    mem2 = ConversationMemory(limit=0)
    assert mem2.limit == 1


def test_conversation_memory_get_context_clamps():
    mem = ConversationMemory(limit=5)
    for i in range(10):
        mem.add("a", f"line {i}", f"ligne {i}")
    assert len(mem.get_context(limit=999)) == 5


def test_smart_buffer_rejects_empty_chunk():
    buf = SmartBuffer(max_size_mb=1)
    assert buf.add_chunk(b"", Priority.NORMAL) is False
    assert buf.add_chunk(b"audio", Priority.NORMAL) is True


def test_stage_metrics_ignores_negative_ms():
    m = StageMetrics("stt")
    m.record(-5)
    m.record(None)
    assert m.count == 0
    m.record(10)
    assert m.count == 1


def test_streaming_sanitize_language_rejects_unknown():
    assert _sanitize_language_code("ht", "en") == "ht"
    assert _sanitize_language_code("xx", "en") == "en"
    assert _sanitize_language_code("HT-fr", "en") == "ht"


def test_sanitize_text_for_tts_strips_placeholders_and_urls():
    cleaned = sanitize_text_for_tts("[en->es] hello https://example.com test")
    assert "[en->" not in cleaned
    assert "https://" not in cleaned
    assert "hello" in cleaned
    assert "test" in cleaned


def test_streaming_sanitize_session_id():
    assert _sanitize_session_id("  room-1  ") == "room-1"
    assert _sanitize_session_id("a" * 200, "default") == "a" * 128
    assert _sanitize_session_id("bad id!", "default") == "badid"
    assert _sanitize_session_id("", "default") == "default"
