import os

from backend.cip_client import call_cip_brain, cip_health_snapshot, cip_settings


class temporary_env:
    def __init__(self, **values):
        self.values = values
        self.previous = {}

    def __enter__(self):
        for key, value in self.values.items():
            self.previous[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def __exit__(self, exc_type, exc, tb):
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_cip_uses_local_brain_by_default_without_localhost_fallback():
    with temporary_env(CIP_PROCESS_URL=None, CIP_DEFAULT_MODE=None):
        settings = cip_settings()

    assert settings["process_url"] == ""
    assert settings["external_configured"] is False
    assert settings["local_enabled"] is True
    assert settings["enabled"] is True
    assert settings["provider"] == "local"
    assert settings["local_engine"] == "python_ai_brain_v8"


def test_cip_health_snapshot_uses_local_when_external_unconfigured():
    with temporary_env(CIP_PROCESS_URL=None, CIP_DEFAULT_MODE="cip_first"):
        snapshot = cip_health_snapshot()

    assert snapshot["reachable"] is True
    assert snapshot["external_reachable"] is False
    assert snapshot["status"] == "local"
    assert snapshot["external_error"] == "not_configured"
    assert snapshot["error"] is None


def test_cip_mode_off_is_noop():
    with temporary_env(CIP_PROCESS_URL="http://127.0.0.1:1/process", CIP_DEFAULT_MODE="off"):
        result = call_cip_brain("hello", "es", "test", fallback_translation="hola")

    assert result is None


def test_cip_local_brain_returns_decision_with_fallback_translation():
    with temporary_env(CIP_PROCESS_URL="http://127.0.0.1:1/process", CIP_DEFAULT_MODE="ut_first"):
        result = call_cip_brain("hello how are you", "es", "test", fallback_translation="hola como estas")

    assert result["provider"] == "local"
    assert result["translation_source"] == "UT+CIP"
    assert result["translated"] == "hola como estas"
    assert result["decision"]["type"] == "response"


def test_cip_local_brain_requests_clarification_for_placeholder_translation():
    with temporary_env(CIP_PROCESS_URL=None, CIP_DEFAULT_MODE="ut_first"):
        result = call_cip_brain("can you check the charge", "es", "test", fallback_translation="[en->es] can you check the charge")

    assert result["provider"] == "local"
    assert result["translated"] == ""
    assert result["decision"]["type"] == "clarification"
    assert "message" in result["decision"]
