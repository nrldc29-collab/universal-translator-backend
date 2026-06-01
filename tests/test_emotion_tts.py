"""Tests for emotion-aware TTS (feature #8: emotional tone preservation).

Covers the pure emotion -> backend-parameter mappings and that synthesize()
threads the emotion_config through to the renderer. No TTS engine required.
"""
import math

from tts.piper_tts import (
    PiperTextToSpeech,
    espeak_flags_from_emotion,
    google_audio_config_from_emotion,
    _piper_synthesis_config_from_emotion,
)


# ── Google Cloud TTS mapping ──────────────────────────────────────────────────

def test_google_none_yields_no_overrides():
    assert google_audio_config_from_emotion(None) == {}


def test_google_neutral_emotion_yields_no_overrides():
    neutral = {"speed": 1.0, "pitch_shift": 0, "volume": 1.0}
    assert google_audio_config_from_emotion(neutral) == {}


def test_google_maps_speed_to_speaking_rate():
    assert google_audio_config_from_emotion({"speed": 1.5})["speakingRate"] == 1.5


def test_google_clamps_speaking_rate():
    assert google_audio_config_from_emotion({"speed": 99})["speakingRate"] == 4.0
    assert google_audio_config_from_emotion({"speed": 0.01})["speakingRate"] == 0.25


def test_google_maps_and_clamps_pitch():
    assert google_audio_config_from_emotion({"pitch_shift": 5})["pitch"] == 5.0
    assert google_audio_config_from_emotion({"pitch_shift": 999})["pitch"] == 20.0
    assert google_audio_config_from_emotion({"pitch_shift": -999})["pitch"] == -20.0


def test_google_maps_volume_to_gain_db():
    cfg = google_audio_config_from_emotion({"volume": 2.0})
    assert cfg["volumeGainDb"] == round(20.0 * math.log10(2.0), 3)


# ── eSpeak NG mapping ─────────────────────────────────────────────────────────

def test_espeak_neutral_matches_baseline():
    assert espeak_flags_from_emotion(None) == (160, 50, 100)
    assert espeak_flags_from_emotion({"speed": 1.0, "pitch_shift": 0, "volume": 1.0}) == (160, 50, 100)


def test_espeak_excited_profile():
    assert espeak_flags_from_emotion({"speed": 1.25, "pitch_shift": 4, "volume": 1.2}) == (200, 60, 120)


def test_espeak_clamps_ranges():
    assert espeak_flags_from_emotion({"speed": 10, "pitch_shift": 100, "volume": 10}) == (450, 99, 200)


# ── Piper SynthesisConfig (graceful when piper unavailable) ───────────────────

def test_piper_config_none_for_empty():
    assert _piper_synthesis_config_from_emotion(None) is None


def test_piper_config_is_safe_regardless_of_piper_install():
    # Must never raise; returns a SynthesisConfig if piper is installed, else None.
    result = _piper_synthesis_config_from_emotion({"speed": 1.5, "volume": 1.2})
    if result is not None:
        assert hasattr(result, "length_scale")


# ── synthesize() threads emotion_config to the renderer ───────────────────────

def test_synthesize_forwards_emotion_config_to_google(monkeypatch, tmp_path):
    tts = PiperTextToSpeech()
    captured = {}

    def fake_google(text, out_path, lang, google_api_key=None, emotion_config=None):
        captured["emotion_config"] = emotion_config
        return str(out_path)

    monkeypatch.setattr(tts, "_use_cloud_tts", lambda *a, **k: True)
    monkeypatch.setattr(tts, "_synthesize_google", fake_google)

    emotion = {"speed": 1.3, "pitch_shift": 2, "volume": 1.1}
    tts.synthesize("hello", str(tmp_path / "out.wav"), language="es", emotion_config=emotion)

    assert captured["emotion_config"] == emotion


def test_synthesize_without_emotion_passes_none(monkeypatch, tmp_path):
    tts = PiperTextToSpeech()
    captured = {}

    def fake_google(text, out_path, lang, google_api_key=None, emotion_config=None):
        captured["emotion_config"] = emotion_config
        return str(out_path)

    monkeypatch.setattr(tts, "_use_cloud_tts", lambda *a, **k: True)
    monkeypatch.setattr(tts, "_synthesize_google", fake_google)

    tts.synthesize("hello", str(tmp_path / "out.wav"), language="es")

    assert captured["emotion_config"] is None
