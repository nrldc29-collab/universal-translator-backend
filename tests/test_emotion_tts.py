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
from backend.tts_pacing import build_tts_pacing, emotion_config_from_style, natural_baseline_emotion_config


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

def test_piper_config_applies_natural_baseline_when_empty():
    result = _piper_synthesis_config_from_emotion(None)
    if result is not None:
        assert getattr(result, "length_scale", None) is not None


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

    monkeypatch.setattr(tts, "_prefer_edge_tts", lambda *a, **k: False)
    monkeypatch.setattr(tts, "_use_cloud_tts", lambda *a, **k: True)
    monkeypatch.setattr(tts, "_synthesize_google", fake_google)

    emotion = {"speed": 1.3, "pitch_shift": 2, "volume": 1.1}
    tts.synthesize("hello", str(tmp_path / "out.wav"), language="es", emotion_config=emotion)

    assert captured["emotion_config"]["speed"] == emotion["speed"]
    assert captured["emotion_config"]["pitch_shift"] == emotion["pitch_shift"]


def test_synthesize_without_emotion_uses_natural_baseline(monkeypatch, tmp_path):
    tts = PiperTextToSpeech()
    captured = {}

    def fake_google(text, out_path, lang, google_api_key=None, emotion_config=None):
        captured["emotion_config"] = emotion_config
        return str(out_path)

    monkeypatch.setattr(tts, "_prefer_edge_tts", lambda *a, **k: False)
    monkeypatch.setattr(tts, "_use_cloud_tts", lambda *a, **k: True)
    monkeypatch.setattr(tts, "_synthesize_google", fake_google)

    tts.synthesize("hello", str(tmp_path / "out.wav"), language="es")

    assert captured["emotion_config"] == natural_baseline_emotion_config()


# ── Pacing style -> emotion_config (live streaming path) ──────────────────────

def test_pacing_style_none_returns_baseline():
    assert emotion_config_from_style(None) == natural_baseline_emotion_config()


def test_pacing_neutral_style_uses_conversational_defaults(monkeypatch):
    monkeypatch.delenv("TTS_NEURAL_MINIMAL_PROCESSING", raising=False)
    cfg = emotion_config_from_style({"speed": 1.0, "pitch": 1.0})
    assert cfg["speed"] == 1.0
    assert "pitch_shift" in cfg


def test_neural_minimal_baseline_avoids_artificial_slowdown(monkeypatch):
    monkeypatch.setenv("TTS_NEURAL_MINIMAL_PROCESSING", "1")
    cfg = emotion_config_from_style({"speed": 0.94, "pitch": 0.98})
    assert cfg["speed"] == 1.0
    assert cfg["pitch_shift"] == 0


def test_pacing_excited_style_maps_speed_and_pitch():
    cfg = emotion_config_from_style({"speed": 1.2, "pitch": 1.1})
    assert cfg["speed"] == 1.2
    assert cfg["pitch_shift"] == round(12.0 * math.log2(1.1), 3)
    assert cfg["pitch_shift"] > 0


def test_pacing_apologetic_style_lowers_pitch():
    cfg = emotion_config_from_style({"speed": 0.85, "pitch": 0.95})
    assert cfg["speed"] == 0.85
    assert cfg["pitch_shift"] == round(12.0 * math.log2(0.95), 3)
    assert cfg["pitch_shift"] < 0


def test_pacing_energy_maps_to_volume():
    cfg = emotion_config_from_style({"speed": 1.0, "pitch": 1.0, "energy": 1.3})
    assert cfg["volume"] == 1.3


def test_apologetic_utterance_produces_applied_emotion_config():
    # End-to-end: pacing detects emotion -> style -> emotion_config the renderer applies.
    pacing = build_tts_pacing("I am so sorry, please forgive me.")
    assert pacing["emotion"] == "apologetic"
    cfg = emotion_config_from_style(pacing["style"])
    assert cfg is not None
    assert cfg["speed"] == 0.85
