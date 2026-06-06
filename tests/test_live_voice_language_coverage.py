from pathlib import Path

from backend.streaming import _should_use_backend_live_tts
from tts.piper_tts import PiperTextToSpeech


CONFIGURED_TARGET_LANGUAGES = {
    "en",
    "es",
    "ht",
    "fr",
    "de",
    "it",
    "pt",
    "nl",
    "ru",
    "zh",
    "ja",
    "ko",
    "ar",
    "hi",
}


def test_all_configured_targets_are_backend_live_voice_languages():
    assert {lang for lang in CONFIGURED_TARGET_LANGUAGES if _should_use_backend_live_tts(lang)} == CONFIGURED_TARGET_LANGUAGES


def test_missing_piper_voice_uses_edge_before_english_fallback(monkeypatch, tmp_path):
    engine = PiperTextToSpeech()
    calls = []

    def fake_edge(text, out_path, lang, emotion_config=None):
        calls.append((text, lang))
        Path(out_path).write_bytes(b"fake wav bytes")
        return str(out_path)

    monkeypatch.setattr(engine, "_synthesize_edge_tts", fake_edge)

    output_path = tmp_path / "nl.wav"
    assert engine.synthesize("Hallo.", str(output_path), language="nl") == str(output_path)
    assert calls == [("Hallo.", "nl")]


def test_no_piper_voice_languages_try_edge_before_espeak(monkeypatch, tmp_path):
    engine = PiperTextToSpeech()
    calls = []

    def fake_edge(text, out_path, lang, emotion_config=None):
        calls.append(lang)
        Path(out_path).write_bytes(b"fake wav bytes")
        return str(out_path)

    def fail_espeak(*args, **kwargs):
        raise AssertionError("eSpeak should not run when Edge TTS succeeds")

    monkeypatch.setattr(engine, "_synthesize_edge_tts", fake_edge)
    monkeypatch.setattr(engine, "_synthesize_espeak", fail_espeak)

    for lang in ("ht", "ja", "ko"):
        output_path = tmp_path / f"{lang}.wav"
        assert engine.synthesize("Hello.", str(output_path), language=lang) == str(output_path)

    assert calls == ["ht", "ja", "ko"]
