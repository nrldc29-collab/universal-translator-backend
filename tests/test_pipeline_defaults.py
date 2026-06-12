import inspect

from backend.config import get_translation_backend, get_whisper_model_size
from backend.pipeline import AnaiTranslatorPipeline
from translation.hybrid_translator import HybridTranslator
from translation.lightweight_translator import LightweightTranslator
from translation.marian_translator import MarianTranslator


def test_pipeline_defaults_target_haitian_creole():
    sig = inspect.signature(AnaiTranslatorPipeline.translate_text)
    assert sig.parameters["target_language"].default == "ht"

    sig_with = inspect.signature(AnaiTranslatorPipeline.translate_text_with)
    assert sig_with.parameters["target_language"].default == "ht"

    sig_audio = inspect.signature(AnaiTranslatorPipeline.translate_audio)
    assert sig_audio.parameters["target_language"].default == "ht"


def test_default_translation_backend_is_resilient_hybrid(monkeypatch):
    monkeypatch.delenv("TRANSLATION_BACKEND", raising=False)
    assert get_translation_backend() == "hybrid"


def test_default_whisper_model_is_realtime_cpu_base(monkeypatch):
    monkeypatch.delenv("WHISPER_MODEL_SIZE", raising=False)
    assert get_whisper_model_size() == "base"


def test_translator_module_defaults_target_haitian_creole():
    marian = MarianTranslator()
    assert marian.default_target_language == "ht"

    lightweight = LightweightTranslator()
    assert lightweight.translate("hello") == "bonjou"
    assert lightweight.translate("I need help") == "mwen bezwen èd"
    assert HybridTranslator.is_placeholder_translation("[en->ht] hello", None, None)
