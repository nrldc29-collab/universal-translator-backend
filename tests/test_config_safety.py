import os

from backend import config


def test_invalid_integer_env_falls_back(monkeypatch):
    monkeypatch.setenv("MAX_AUDIO_MB", "not-a-number")

    assert config.get_max_audio_mb() == 25


def test_numeric_env_values_are_clamped(monkeypatch):
    monkeypatch.setenv("REQUESTS_PER_MINUTE", "0")
    monkeypatch.setenv("CIP_CONFIDENCE_THRESHOLD", "2")

    assert config.get_requests_per_minute() == 1
    assert config.get_cip_confidence_threshold() == 1.0


def test_boolean_env_parsing(monkeypatch):
    monkeypatch.setenv("PARTIAL_TTS_MODE", "off")
    monkeypatch.setenv("PRELOAD_MODELS", "yes")

    assert config.get_partial_tts_mode() is False
    assert config.get_preload_models() is True
