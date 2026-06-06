"""Tests for backend.glossary."""

from backend.glossary import (
    DEFAULT_GLOSSARY,
    apply_glossary_substitutions,
    find_glossary_matches,
    get_session_glossary,
    glossary_coverage_score,
    prepare_for_translation,
    finalize_translation,
    protect_medical_terms,
    restore_protected_terms,
    set_session_glossary,
)


def test_protect_and_restore_medical_terms():
    protected, applied = protect_medical_terms("Take 500mg ibuprofen for pain")
    assert applied is True
    assert "[KEEP]ibuprofen[/KEEP]" in protected
    restored = restore_protected_terms(protected)
    assert restored == "Take 500mg ibuprofen for pain"


def test_apply_glossary_en_to_es():
    source = "My blood pressure is high"
    translated = "Mi presión es alta"
    result, applied = apply_glossary_substitutions(
        source, translated, DEFAULT_GLOSSARY, "en", "es"
    )
    assert applied is True
    assert "presión arterial" in result.lower()


def test_apply_glossary_en_to_ht():
    source = "I need help now"
    translated = "Mwen bezwen kèk bagay"
    result, applied = apply_glossary_substitutions(
        source, translated, DEFAULT_GLOSSARY, "en", "ht"
    )
    assert applied is True
    assert "èd" in result.lower()


def test_session_glossary_merges_with_defaults():
    set_session_glossary("test-session", [{"source": "widget", "target": "widgeto", "lang_pair": "en-es"}])
    merged = get_session_glossary("test-session")
    assert any(entry.get("source") == "widget" for entry in merged)
    assert any(entry.get("source") == "blood pressure" for entry in merged)


def test_glossary_coverage_score():
    matches = find_glossary_matches("blood pressure check", DEFAULT_GLOSSARY, "en", "es")
    assert matches
    score = glossary_coverage_score(
        "blood pressure check",
        "presión arterial alta",
        DEFAULT_GLOSSARY,
        "en",
        "es",
    )
    assert score == 1.0


def test_finalize_translation_restores_protected_terms():
    prepared, meta = prepare_for_translation("Take ibuprofen", strict_medical=True)
    assert meta["protected_terms"] is True
    raw_translation = prepared.replace("ibuprofen", "ibuprofeno")
    final, final_meta = finalize_translation(
        "Take ibuprofen",
        raw_translation,
        session_id="finalize-test",
        source_lang="en",
        target_lang="es",
        strict_medical=True,
        metadata=meta,
    )
    assert "ibuprofen" in final.lower() or "ibuprofeno" in final.lower()
    assert "glossary_applied" in final_meta


class FakePassThroughTranslator:
    def translate(self, text, source_language=None, target_language=None):
        return text


def test_translate_local_preserves_medical_terms():
    from backend.pipeline import AnaiTranslatorPipeline

    pipeline = AnaiTranslatorPipeline(translator=FakePassThroughTranslator(), enable_ailang=False)
    result = pipeline.translate_local(
        "Take ibuprofen for pain",
        "en",
        "es",
        original_source_text="Take ibuprofen for pain",
    )
    assert "ibuprofen" in result.lower()
