"""Tests for backend.refine - translation refinement helpers."""
import pytest
from backend.refine import (
    _clean_spacing,
    _sentence_case,
    apply_context_memory,
    refine_translation,
)


class TestCleanSpacing:
    def test_collapses_multiple_spaces(self):
        assert _clean_spacing("hello   world") == "hello world"

    def test_strips_leading_trailing_whitespace(self):
        assert _clean_spacing("  hello  ") == "hello"

    def test_removes_space_before_punctuation(self):
        assert _clean_spacing("hello , world") == "hello, world"

    def test_removes_space_before_exclamation(self):
        assert _clean_spacing("hello !") == "hello!"

    def test_handles_empty_string(self):
        assert _clean_spacing("") == ""

    def test_handles_none(self):
        assert _clean_spacing(None) == ""


class TestSentenceCase:
    def test_capitalizes_first_letter(self):
        assert _sentence_case("hello world") == "Hello world"

    def test_preserves_rest_of_string(self):
        assert _sentence_case("hello WORLD") == "Hello WORLD"

    def test_handles_empty_string(self):
        assert _sentence_case("") == ""

    def test_handles_already_capitalized(self):
        assert _sentence_case("Hello") == "Hello"


class TestApplyContextMemory:
    def test_returns_text_unchanged_without_history(self):
        assert apply_context_memory("Hello", {}) == "Hello"

    def test_restores_named_terms_from_conversation_history(self):
        context = [{"source_text": "Meet Marie at CVS.", "translated_text": "..."}]
        result = apply_context_memory("marie called", context)
        assert "Marie" in result

    def test_restores_quoted_names_from_source(self):
        result = refine_translation('Call "Marie" now.', 'appelez marie maintenant.')
        assert "Marie" in result


class TestRefineTranslation:
    def test_removes_uh_filler(self):
        result = refine_translation("uh source", "uh hello there")
        assert "uh" not in result.lower()

    def test_removes_um_filler(self):
        result = refine_translation("source", "um it was great")
        assert result.startswith("It") or "um" not in result.lower()

    def test_sentence_case_applied(self):
        result = refine_translation("src", "hello world")
        assert result[0].isupper()

    def test_empty_translation_returns_empty(self):
        assert refine_translation("source", "") == ""

    def test_none_translation_returns_empty(self):
        assert refine_translation("source", None) == ""

    def test_cleans_extra_spaces(self):
        result = refine_translation("src", "hello   world")
        assert "  " not in result

    def test_preserves_meaning(self):
        result = refine_translation("hello", "Hola, ¿cómo estás?")
        assert "Hola" in result
        assert "estás" in result

    def test_does_not_inject_capitalized_greeting_as_a_name(self):
        assert refine_translation("Hello", "Hola") == "Hola"

    def test_does_not_inject_cjk_source_text_as_a_name(self):
        assert refine_translation("\u3053\u3093\u306b\u3061\u306f", "Hello.") == "Hello."

    def test_restores_proper_noun_casing_from_source(self):
        result = refine_translation("Meet Marie at CVS.", "Rencontrez marie à cvs.")
        assert "Marie" in result
        assert "CVS" in result

    def test_injects_missing_proper_nouns(self):
        result = refine_translation("Call Marie tomorrow.", "Llámame mañana.")
        assert "Marie" in result

    def test_preserves_target_like_when_not_in_source(self):
        result = refine_translation("I enjoy music.", "Me gusta la música.")
        assert "gusta" in result.lower()
