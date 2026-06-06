"""Regression tests for pipeline.translate_text_with and api._translator_for_request."""
import pytest
from unittest.mock import MagicMock
from backend.pipeline import AnaiTranslatorPipeline, TranslationResult


class FakeTranslator:
    def __init__(self, response="translated"):
        self.response = response
        self.calls = []

    def translate(self, text, source_language=None, target_language=None):
        self.calls.append((text, source_language, target_language))
        return self.response


class FakeContextLayer:
    def improve(self, text, src, tgt, tone):
        return text


class FakeTts:
    def synthesize(self, text, path, language=None):
        return path

    def preload(self):
        return {}


class FakeStt:
    def transcribe(self, path, lang):
        return "hello"

    def preload(self):
        return {}


def make_pipeline(translator=None):
    p = AnaiTranslatorPipeline.__new__(AnaiTranslatorPipeline)
    p.stt = FakeStt()
    p.translator = translator or FakeTranslator("default output")
    p.tts = FakeTts()
    p.context_layer = FakeContextLayer()
    p.session_id = "default"
    p.enable_ailang = False
    p.ailang_pipeline = None
    return p


# ── translate_text_with ──────────────────────────────────────────────────────

def test_translate_text_with_uses_supplied_translator():
    pipeline = make_pipeline()
    override = FakeTranslator("override output")

    result = pipeline.translate_text_with(override, text="hello", source_language="en", target_language="es")

    assert result.translated_text == "override output"
    assert override.calls == [("hello", "en", "es")]


def test_translate_text_with_does_not_mutate_pipeline_translator():
    default = FakeTranslator("default output")
    pipeline = make_pipeline(translator=default)
    override = FakeTranslator("override output")

    pipeline.translate_text_with(override, text="hello", source_language="en", target_language="es")

    assert pipeline.translator is default
    assert default.calls == []


def test_translate_text_with_empty_returns_empty():
    pipeline = make_pipeline()
    override = FakeTranslator("should not be called")

    result = pipeline.translate_text_with(override, text="   ", source_language="en", target_language="es")

    assert result.translated_text == ""
    assert override.calls == []


def test_translate_text_with_returns_translation_result():
    pipeline = make_pipeline()
    override = FakeTranslator("hola")

    result = pipeline.translate_text_with(override, text="hello", source_language="en", target_language="es")

    assert isinstance(result, TranslationResult)
    assert result.source_text == "hello"
    assert result.translated_text == "hola"
    assert result.audio_output_path is None


# ── _translator_for_request ──────────────────────────────────────────────────

def test_translator_for_request_none_when_no_override():
    from backend.api import _translator_for_request
    assert _translator_for_request(None, None) is None


def test_translator_for_request_none_when_empty_strings():
    from backend.api import _translator_for_request
    assert _translator_for_request("", "") is None


def test_translator_for_request_lightweight_for_fast_mode():
    from backend.api import _translator_for_request
    from translation import LightweightTranslator
    result = _translator_for_request("fast", None)
    assert isinstance(result, LightweightTranslator)


def test_translator_for_request_hybrid_for_balanced_mode():
    from backend.api import _translator_for_request
    from translation import HybridTranslator
    result = _translator_for_request("balanced", None)
    assert isinstance(result, HybridTranslator)


def test_translator_for_request_hybrid_for_hybrid_provider():
    from backend.api import _translator_for_request
    from translation import HybridTranslator
    result = _translator_for_request(None, "hybrid")
    assert isinstance(result, HybridTranslator)


def test_translator_for_request_lightweight_for_lightweight_provider():
    from backend.api import _translator_for_request
    from translation import LightweightTranslator
    result = _translator_for_request(None, "lightweight")
    assert isinstance(result, LightweightTranslator)


def test_translator_for_request_remote_uses_marian():
    from backend.api import _translator_for_request
    from translation.marian_translator import MarianTranslator

    result = _translator_for_request(None, "remote")
    assert isinstance(result, MarianTranslator)


def test_translator_for_request_unknown_returns_none():
    from backend.api import _translator_for_request
    result = _translator_for_request("unknown_mode", "unknown_provider")
    assert result is None
