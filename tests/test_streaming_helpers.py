"""Tests for backend.streaming_helpers pure functions."""

import pytest
from unittest.mock import patch

import json

from backend.streaming_helpers import (
    chunk_text_for_tts,
    should_translate_partial,
    normalize_live_text,
    normalized_word,
    folded_live_text,
    live_translation_delta,
    is_speakable_live_delta,
    audio_suffix_for_mime,
    resolve_stream_audio_mode,
    extract_client_voice_active,
    parse_provider_event,
)


class TestResolveStreamAudioMode:
    def test_default_is_pcm16(self):
        assert resolve_stream_audio_mode() == (True, ".wav")

    def test_explicit_pcm16_format(self):
        assert resolve_stream_audio_mode("pcm16") == (True, ".wav")
        assert resolve_stream_audio_mode("s16le") == (True, ".wav")
        assert resolve_stream_audio_mode(".raw") == (True, ".wav")

    def test_compressed_format_needs_transcode(self):
        assert resolve_stream_audio_mode("m4a") == (False, ".m4a")
        assert resolve_stream_audio_mode("webm") == (False, ".webm")

    def test_mime_type_pcm_is_pcm16(self):
        assert resolve_stream_audio_mode(None, "audio/pcm") == (True, ".wav")
        assert resolve_stream_audio_mode(None, "audio/L16") == (True, ".wav")

    def test_mime_type_compressed_needs_transcode(self):
        assert resolve_stream_audio_mode(None, "audio/mp4") == (False, ".m4a")
        assert resolve_stream_audio_mode(None, "audio/webm") == (False, ".webm")

    def test_format_takes_precedence_over_mime(self):
        assert resolve_stream_audio_mode("m4a", "audio/pcm") == (False, ".m4a")


class TestBuildStreamingRepair:
    def test_high_confidence_no_repair(self):
        from backend.streaming_helpers import build_streaming_repair
        assert build_streaming_repair("hello there friend", None, 0.9) == []

    def test_prefers_cip_repair_options(self):
        from backend.streaming_helpers import build_streaming_repair
        plan = {"repair_options": [{"type": "repeat_terms", "terms": ["Maria"]}]}
        assert build_streaming_repair("call maria", plan, 0.9) == plan["repair_options"]

    def test_local_choose_meaning_for_ambiguous_word(self):
        from backend.streaming_helpers import build_streaming_repair
        options = build_streaming_repair("go to the bank", None, 0.1)
        assert any(o["type"] == "choose_meaning" and o["word"] == "bank" for o in options)

    def test_local_repeat_slowly_fallback(self):
        from backend.streaming_helpers import build_streaming_repair
        options = build_streaming_repair("zzzz", None, 0.1)
        assert options and options[0]["type"] == "repeat_slowly"


# ---------------------------------------------------------------------------
# chunk_text_for_tts
# ---------------------------------------------------------------------------

def test_chunk_text_for_tts_short_text_returns_single_chunk():
    with patch("backend.streaming_helpers.get_tts_first_chunk_chars", return_value=120), \
         patch("backend.streaming_helpers.get_tts_chunk_chars", return_value=120):
        chunks = chunk_text_for_tts("Hello world", max_chars=120)
    assert chunks == ["Hello world"]


def test_chunk_text_for_tts_empty_returns_original():
    chunks = chunk_text_for_tts("", max_chars=50)
    assert chunks == [""]


def test_chunk_text_for_tts_splits_at_punctuation():
    text = "Hello. How are you? I am fine."
    chunks = chunk_text_for_tts(text, max_chars=20)
    assert len(chunks) >= 2
    assert all(len(c) <= 20 for c in chunks)


def test_chunk_text_for_tts_first_chunk_is_short():
    """The first chunk should be capped at TTS_FIRST_CHUNK_CHARS for faster playback start."""
    long_text = "The quick brown fox jumps over the lazy dog and then runs away into the forest."
    with patch("backend.streaming_helpers.get_tts_first_chunk_chars", return_value=10), \
         patch("backend.streaming_helpers.get_tts_chunk_chars", return_value=80):
        chunks = chunk_text_for_tts(long_text)
    assert len(chunks[0]) <= 10


def test_chunk_text_for_tts_no_empty_chunks():
    text = "This is a sentence. And another one. And a third."
    chunks = chunk_text_for_tts(text, max_chars=30)
    assert all(c.strip() for c in chunks)


# ---------------------------------------------------------------------------
# should_translate_partial
# ---------------------------------------------------------------------------

def test_should_translate_partial_empty_returns_false():
    assert should_translate_partial("") is False
    assert should_translate_partial("   ") is False


def test_should_translate_partial_ends_with_punctuation():
    assert should_translate_partial("Hello,") is True
    assert should_translate_partial("Hello.") is True
    assert should_translate_partial("Really?") is True
    assert should_translate_partial("Stop!") is True


def test_should_translate_partial_long_enough_returns_true():
    with patch("backend.streaming_helpers.get_partial_translation_min_words", return_value=3):
        assert should_translate_partial("one two three") is True
        assert should_translate_partial("one two") is False


def test_should_translate_partial_short_no_punct_returns_false():
    with patch("backend.streaming_helpers.get_partial_translation_min_words", return_value=5):
        assert should_translate_partial("hello there") is False


# ---------------------------------------------------------------------------
# normalize_live_text
# ---------------------------------------------------------------------------

def test_normalize_live_text_collapses_whitespace():
    assert normalize_live_text("  hello   world  ") == "hello world"


def test_normalize_live_text_handles_none_like_empty():
    assert normalize_live_text("") == ""


def test_normalize_live_text_tabs_and_newlines():
    assert normalize_live_text("hello\t\nworld") == "hello world"


# ---------------------------------------------------------------------------
# normalized_word
# ---------------------------------------------------------------------------

def test_normalized_word_strips_punctuation():
    assert normalized_word("hello,") == "hello"
    assert normalized_word('"world"') == "world"


def test_normalized_word_lowercases():
    assert normalized_word("HELLO") == "hello"


def test_normalized_word_strips_diacritics():
    assert normalized_word("caf\xe9") == "cafe"


def test_normalized_word_empty():
    assert normalized_word("") == ""


# ---------------------------------------------------------------------------
# folded_live_text
# ---------------------------------------------------------------------------

def test_folded_live_text_normalizes_all_words():
    result = folded_live_text("  Caf\xe9  World! ")
    assert result == "cafe world"


# ---------------------------------------------------------------------------
# live_translation_delta
# ---------------------------------------------------------------------------

def test_live_translation_delta_empty_previous_returns_current():
    assert live_translation_delta("", "hello world") == "hello world"


def test_live_translation_delta_empty_current_returns_empty():
    assert live_translation_delta("hello", "") == ""


def test_live_translation_delta_prefix_returns_new_words():
    delta = live_translation_delta("hello", "hello world")
    assert delta == "world"


def test_live_translation_delta_full_match_returns_empty():
    assert live_translation_delta("hello world", "hello world") == ""


def test_live_translation_delta_case_insensitive_prefix():
    delta = live_translation_delta("Hello", "hello world")
    assert delta == "world"


def test_live_translation_delta_no_overlap_returns_empty():
    assert live_translation_delta("abc def", "xyz pqr") == ""


# ---------------------------------------------------------------------------
# is_speakable_live_delta
# ---------------------------------------------------------------------------

def test_is_speakable_live_delta_requires_word_char():
    assert is_speakable_live_delta("hi") is True
    assert is_speakable_live_delta("  ") is False
    assert is_speakable_live_delta("!") is False


def test_is_speakable_live_delta_requires_min_length():
    assert is_speakable_live_delta("a") is False
    assert is_speakable_live_delta("ab") is True


# ---------------------------------------------------------------------------
# audio_suffix_for_mime
# ---------------------------------------------------------------------------

def test_audio_suffix_for_mime_mp4():
    assert audio_suffix_for_mime("audio/mp4") == ".m4a"
    assert audio_suffix_for_mime("audio/aac") == ".m4a"
    assert audio_suffix_for_mime("audio/m4a") == ".m4a"


def test_audio_suffix_for_mime_ogg():
    assert audio_suffix_for_mime("audio/ogg") == ".ogg"


def test_audio_suffix_for_mime_wav():
    assert audio_suffix_for_mime("audio/wav") == ".wav"


def test_audio_suffix_for_mime_default_webm():
    assert audio_suffix_for_mime("audio/webm") == ".webm"
    assert audio_suffix_for_mime(None) == ".webm"
    assert audio_suffix_for_mime("") == ".webm"


# ---------------------------------------------------------------------------
# extract_client_voice_active
# ---------------------------------------------------------------------------

def test_extract_client_voice_active_voice_active_key():
    assert extract_client_voice_active({"voice_active": True}) is True


def test_extract_client_voice_active_explicit_key():
    assert extract_client_voice_active({"client_voice_active": True}) is True


def test_extract_client_voice_active_prefers_legacy_key():
    result = extract_client_voice_active({"voice_active": False, "client_voice_active": True})
    assert result is False


def test_extract_client_voice_active_missing_returns_none():
    assert extract_client_voice_active({}) is None


# ---------------------------------------------------------------------------
# parse_provider_event
# ---------------------------------------------------------------------------

def test_parse_provider_event_returns_none_for_invalid_json():
    assert parse_provider_event("not-json") is None
    assert parse_provider_event(b"{{broken") is None
    assert parse_provider_event(None) is None


def test_parse_provider_event_returns_none_for_non_dict_json():
    assert parse_provider_event(json.dumps([1, 2, 3])) is None


def test_parse_provider_event_decodes_bytes():
    raw = json.dumps({"type": "session.started", "session_id": "abc"}).encode()
    event = parse_provider_event(raw)
    assert event is not None
    assert event["type"] == "session.started"
    assert event["session_id"] == "abc"


def test_parse_provider_event_transcript_is_final_true_becomes_final():
    raw = json.dumps({"type": "transcript", "is_final": True, "text": "hello"}).encode()
    event = parse_provider_event(raw)
    assert event["type"] == "transcript.final"


def test_parse_provider_event_transcript_is_final_false_becomes_partial():
    raw = json.dumps({"type": "transcript", "is_final": False, "text": "hel"})
    event = parse_provider_event(raw)
    assert event["type"] == "transcript.partial"


def test_parse_provider_event_transcript_missing_is_final_becomes_partial():
    raw = json.dumps({"type": "transcript", "text": "hello"})
    event = parse_provider_event(raw)
    assert event["type"] == "transcript.partial"


def test_parse_provider_event_session_started_includes_trace_and_sample_rate():
    payload = {
        "type": "session.started",
        "session_id": "sess-1",
        "trace_id": "trace-abc",
        "sample_rate": 16000,
    }
    event = parse_provider_event(json.dumps(payload))
    assert event["type"] == "session.started"
    assert event["session_id"] == "sess-1"
    assert event["trace_id"] == "trace-abc"
    assert event["sample_rate"] == 16000


def test_parse_provider_event_error_event_passthrough():
    raw = json.dumps({"type": "error", "message": "quota exceeded"})
    event = parse_provider_event(raw)
    assert event["type"] == "error"
    assert event["message"] == "quota exceeded"


def test_parse_provider_event_unknown_type_preserved():
    raw = json.dumps({"type": "custom.event", "data": 42})
    event = parse_provider_event(raw)
    assert event["type"] == "custom.event"
