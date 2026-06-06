import inspect

from backend.pipeline import AnaiTranslatorPipeline


def test_pipeline_defaults_target_haitian_creole():
    sig = inspect.signature(AnaiTranslatorPipeline.translate_text)
    assert sig.parameters["target_language"].default == "ht"

    sig_with = inspect.signature(AnaiTranslatorPipeline.translate_text_with)
    assert sig_with.parameters["target_language"].default == "ht"

    sig_audio = inspect.signature(AnaiTranslatorPipeline.translate_audio)
    assert sig_audio.parameters["target_language"].default == "ht"
