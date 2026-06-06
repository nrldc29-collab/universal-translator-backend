import inspect

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


def test_translator_module_defaults_target_haitian_creole():
    marian = MarianTranslator()
    assert marian.default_target_language == "ht"

    lightweight = LightweightTranslator()
    assert lightweight.translate("hello") == "bonjou"
    assert lightweight.translate("I need help") == "mwen bezwen èd"
    assert HybridTranslator.is_placeholder_translation("[en->ht] hello", None, None)
