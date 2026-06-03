import os
import re

from backend import config


def test_allowed_origin_regex_matches_public_tunnel_hosts():
    # The frontend treats these hosting/tunnel domains as valid backend hosts;
    # CORS must allow them or browsers block /health etc. ("Backend offline").
    pattern = re.compile(config.get_allowed_origin_regex())
    allowed = [
        "https://stays-constantly-senators-made.trycloudflare.com",
        "https://my-app.up.railway.app",
        "https://anai.onrender.com",
        "https://anai.fly.dev",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
    ]
    for origin in allowed:
        assert pattern.fullmatch(origin), f"expected {origin} to be allowed"


def test_allowed_origin_regex_rejects_unknown_hosts():
    pattern = re.compile(config.get_allowed_origin_regex())
    for origin in [
        "https://evil.example.com",
        "https://trycloudflare.com.evil.com",
        "https://notrailway.app",
    ]:
        assert not pattern.fullmatch(origin), f"expected {origin} to be rejected"


def test_allowed_origin_regex_is_overridable(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGIN_REGEX", r"https://only\.me")
    assert config.get_allowed_origin_regex() == r"https://only\.me"


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
