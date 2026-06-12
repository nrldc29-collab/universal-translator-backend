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
    live_translation_redundant,
    is_internal_translation_artifact,
    live_translation_delta,
    is_speakable_live_delta,
    audio_suffix_for_bytes,
    audio_suffix_for_mime,
    extract_client_voice_active,
    parse_provider_event,
    run_pipeline_step,
)


@pytest.mark.asyncio
async def test_run_pipeline_step_forwards_keyword_arguments():
    def translate(text, source_language, target_language, *, strict_medical=False):
        return text, source_language, target_language, strict_medical

    result = await run_pipeline_step(
        "translation",
        translate,
        "Take ibuprofen",
        "en",
        "es",
        strict_medical=True,
    )

    assert result == ("Take ibuprofen", "en", "es", True)


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


def test_chunk_text_for_tts_splits_at_punctuation(monkeypatch):
    monkeypatch.setenv("TTS_NATURAL_VOICE", "0")
    text = "Hello. How are you? I am fine."
    chunks = chunk_text_for_tts(text, max_chars=20)
    assert len(chunks) >= 2
    assert all(len(c) <= 20 for c in chunks)


def test_chunk_text_for_tts_first_chunk_is_short(monkeypatch):
    """The first chunk should be capped at TTS_FIRST_CHUNK_CHARS for faster playback start."""
    monkeypatch.setenv("TTS_NATURAL_VOICE", "0")
    long_text = "The quick brown fox jumps over the lazy dog and then runs away into the forest."
    with patch("backend.streaming_helpers.get_tts_first_chunk_chars", return_value=10), \
         patch("backend.streaming_helpers.get_tts_chunk_chars", return_value=80):
        chunks = chunk_text_for_tts(long_text)
    assert len(chunks[0]) <= 10


def test_chunk_text_for_tts_natural_keeps_short_text_whole(monkeypatch):
    monkeypatch.setenv("TTS_NATURAL_VOICE", "1")
    text = "Hello. How are you today? I hope you are well."
    chunks = chunk_text_for_tts(text, natural=True)
    assert chunks == [text]


def test_chunk_text_for_tts_natural_splits_on_sentences_only(monkeypatch):
    monkeypatch.setenv("TTS_NATURAL_VOICE", "1")
    with patch("backend.streaming_helpers.get_tts_max_single_pass_chars", return_value=40):
        text = "First sentence here. Second sentence follows."
        chunks = chunk_text_for_tts(text, natural=True)
    assert len(chunks) == 2
    assert chunks[0] == "First sentence here."
    assert chunks[1] == "Second sentence follows."


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


def test_should_translate_partial_cjk_punctuation():
    assert should_translate_partial("我需要帮助。") is True


def test_should_translate_partial_cjk_length_units():
    with patch("backend.streaming_helpers.get_partial_translation_min_words", return_value=3):
        assert should_translate_partial("我需要帮助") is True


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
# live_translation_redundant
# ---------------------------------------------------------------------------

def test_live_translation_redundant_matches_exact_text():
    assert live_translation_redundant("Merci beaucoup.", "merci beaucoup") is True


def test_live_translation_redundant_matches_reordered_words():
    assert live_translation_redundant("Большое спасибо.", "Спасибо большое.") is True


def test_live_translation_redundant_allows_fuller_translation():
    assert live_translation_redundant("Спасибо.", "Большое спасибо.") is False


def test_live_translation_redundant_returns_false_without_previous():
    assert live_translation_redundant("", "Спасибо.") is False


# ---------------------------------------------------------------------------
# is_internal_translation_artifact
# ---------------------------------------------------------------------------

def test_is_internal_translation_artifact_rejects_ai_stub_prompt():
    text = "[AI:fast] Ensure this French uses vous (formal). Keep meaning: [en->None] Hello..."
    assert is_internal_translation_artifact(text) is True


def test_is_internal_translation_artifact_rejects_placeholder_translation():
    assert is_internal_translation_artifact("[en->fr] Hello") is True


def test_is_internal_translation_artifact_allows_real_translation():
    assert is_internal_translation_artifact("Bonjour.") is False


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


def test_audio_suffix_for_bytes_prefers_container_over_mime():
    assert audio_suffix_for_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt ", "audio/mp4") == ".wav"
    assert audio_suffix_for_bytes(b"\x1a\x45\xdf\xa3webm-data", "audio/mp4") == ".webm"
    assert audio_suffix_for_bytes(b"OggS\x00\x02", "audio/mp4") == ".ogg"
    assert audio_suffix_for_bytes(b"\x00\x00\x00\x18ftypM4A ", "audio/webm") == ".m4a"


def test_audio_suffix_for_bytes_falls_back_to_mime():
    assert audio_suffix_for_bytes(b"\x00\x00\x01D", "audio/aac") == ".m4a"
    assert audio_suffix_for_bytes(b"", "audio/ogg") == ".ogg"


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
