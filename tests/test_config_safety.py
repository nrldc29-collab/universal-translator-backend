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


def test_quota_default_supports_conversation_mode(monkeypatch):
    monkeypatch.delenv("QUOTA_REQUESTS_PER_HOUR", raising=False)

    assert config.get_quota_limit() == 500


def test_boolean_env_parsing(monkeypatch):
    monkeypatch.setenv("PARTIAL_TTS_MODE", "off")
    monkeypatch.setenv("PRELOAD_MODELS", "yes")

    assert config.get_partial_tts_mode() is False
    assert config.get_preload_models() is True


def test_port_env_wins_over_backend_port(monkeypatch):
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("BACKEND_PORT", "8000")

    assert config.get_backend_port() == 8080


def test_railway_bootstrap_fills_missing_production_defaults(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("USERS", "demo:demo")
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "my-app.up.railway.app")
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "project-abc")
    monkeypatch.setenv("RAILWAY_SERVICE_ID", "service-xyz")

    applied = config.apply_railway_production_defaults()
    assert "JWT_SECRET" in applied
    assert "USERS" in applied
    assert "ALLOWED_ORIGINS" in applied
    assert "BACKEND_HOST" in applied
    assert config.validate_production_config() == []
    assert config.get_allowed_origins() == ["https://my-app.up.railway.app"]
    assert config.get_backend_host() == "0.0.0.0"
    assert len(config.get_jwt_secret()) >= 32
    assert config.get_users()["demo"]


def test_railway_bootstrap_does_not_override_explicit_secrets(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 64)
    monkeypatch.setenv("USERS", "operator:strong-pass-here")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.mycompany.com")
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "my-app.up.railway.app")
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "project-abc")

    applied = config.apply_railway_production_defaults()
    assert applied == []
    assert config.get_jwt_secret() == "x" * 64
    assert config.get_users() == {"operator": "strong-pass-here"}
    assert config.get_allowed_origins() == ["https://app.mycompany.com"]


def test_railway_bootstrap_disables_blocking_preload(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 64)
    monkeypatch.setenv("USERS", "operator:strong-pass-here")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.mycompany.com")
    monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "my-app.up.railway.app")
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "project-abc")
    monkeypatch.setenv("PRELOAD_MODELS", "1")

    applied = config.apply_railway_production_defaults()
    assert applied == ["PRELOAD_MODELS"]
    assert config.get_preload_models() is False


def test_production_defaults_preload_off_when_unset(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("PRELOAD_MODELS", raising=False)

    assert config.get_preload_models() is False


def test_production_binds_all_interfaces_when_host_loopback(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("BACKEND_HOST", "127.0.0.1")

    assert config.get_backend_host() == "0.0.0.0"
