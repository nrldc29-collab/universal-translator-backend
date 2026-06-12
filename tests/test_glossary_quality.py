"""Tests for glossary-first routing, safety guards, and session corrections."""

from backend.glossary import (
    check_translation_safety,
    find_glossary_matches,
    promote_glossary_correction,
    try_direct_glossary_translation,
    get_session_glossary,
    map_environment_for_stt,
)
from translation.lightweight_translator import LightweightTranslator


def test_map_environment_aliases():
    assert map_environment_for_stt("noisy") == "crowded"
    assert map_environment_for_stt("RESTAURANT") == "restaurant"
    assert map_environment_for_stt("unknown") == "quiet"


def test_direct_glossary_exact_match():
    glossary = get_session_glossary("test-direct")
    result = try_direct_glossary_translation(
        "I need a doctor",
        glossary,
        "en",
        "ht",
    )
    assert result == "Mwen bezwen yon doktè"


def test_word_boundary_glossary_match():
    glossary = get_session_glossary("test-boundary")
    matches = find_glossary_matches("Please call an ambulance now", glossary, "en", "ht")
    assert any(entry["source"].lower().startswith("call an ambulance") for entry in matches)


def test_negation_safety_blocks_unsafe_translation():
    safety = check_translation_safety(
        "I do not need a doctor",
        "Mwen bezwen yon doktè",
        source_lang="en",
        target_lang="ht",
        strict_medical=True,
    )
    assert safety["safe"] is False
    assert "negation_lost" in safety["issues"]
    assert safety["block_tts"] is True


def test_dosage_safety():
    safety = check_translation_safety(
        "Take 500 mg ibuprofen",
        "Pran ibuprofen",
        source_lang="en",
        target_lang="ht",
        strict_medical=True,
    )
    assert safety["safe"] is False
    assert any(issue.startswith("dosage_missing:") for issue in safety["issues"])


def test_promote_glossary_correction_persists_for_session():
    session = "test-promote-session"
    first = promote_glossary_correction(
        session,
        source="My child is sick",
        target="Pitit mwen malad",
        source_lang="en",
        target_lang="ht",
        context="medical",
    )
    assert first["ok"] is True
    second = promote_glossary_correction(
        session,
        source="My child is sick",
        target="Pitit mwen malad",
        source_lang="en",
        target_lang="ht",
    )
    assert second["ok"] is True
    assert second["updated"] is True
    direct = try_direct_glossary_translation(
        "My child is sick",
        get_session_glossary(session),
        "en",
        "ht",
    )
    assert direct == "Pitit mwen malad"


def test_lightweight_partial_prefix():
    translator = LightweightTranslator()
    partial = translator.lookup_phrase_prefix("i need a", "en", "ht")
    assert partial is None or isinstance(partial, str)
