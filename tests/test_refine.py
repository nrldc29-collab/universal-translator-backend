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
    def test_returns_text_unchanged(self):
        assert apply_context_memory("Hello", {}) == "Hello"

    def test_does_not_mutate_with_speaker_context(self):
        assert apply_context_memory("text", {}, speaker_context={"speaker": "A"}) == "text"


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
