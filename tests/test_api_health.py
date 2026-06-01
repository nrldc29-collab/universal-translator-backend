"""Tests for backend.api_health — stt_provider_health_snapshot and runtime_payload."""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from backend.api_health import stt_provider_health_snapshot, runtime_payload, runtime_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_resp(status: int, body: dict):
    """Return a mock urllib response with .status and .read()."""
    raw = json.dumps(body).encode()
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = raw
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# stt_provider_health_snapshot — non-streaming mode
# ---------------------------------------------------------------------------

def test_snapshot_non_streaming_skips_probe():
    with patch("backend.api_health.get_stt_provider", return_value="local"), \
         patch("backend.api_health.get_stt_provider_url", return_value="http://localhost:8000"), \
         patch("backend.api_health.get_stt_provider_ws_url", return_value="ws://localhost:8000"):
        snap = stt_provider_health_snapshot()

    assert snap["mode"] == "local"
    assert snap["reachable"] is None
    assert snap["status_code"] is None
    assert snap["latency_ms"] is None


# ---------------------------------------------------------------------------
# stt_provider_health_snapshot — streaming mode, healthy provider
# ---------------------------------------------------------------------------

def test_snapshot_streaming_reachable_parses_body():
    body = {
        "status": "ok",
        "active_connections": 3,
        "max_active_connections": 100,
        "app": "true-streaming-stt",
    }
    mock_resp = _mock_resp(200, body)

    with patch("backend.api_health.get_stt_provider", return_value="streaming"), \
         patch("backend.api_health.get_stt_provider_url", return_value="http://stt:8002"), \
         patch("backend.api_health.get_stt_provider_ws_url", return_value="ws://stt:8002"), \
         patch("backend.api_health.urlopen", return_value=mock_resp):
        snap = stt_provider_health_snapshot()

    assert snap["reachable"] is True
    assert snap["status_code"] == 200
    assert snap["active_connections"] == 3
    assert snap["max_active_connections"] == 100
    assert snap["provider_app"] == "true-streaming-stt"
    assert snap["latency_ms"] is not None


def test_snapshot_streaming_health_url_uses_slash_health():
    mock_resp = _mock_resp(200, {})

    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        return mock_resp

    with patch("backend.api_health.get_stt_provider", return_value="streaming"), \
         patch("backend.api_health.get_stt_provider_url", return_value="http://stt:8002"), \
         patch("backend.api_health.get_stt_provider_ws_url", return_value="ws://stt:8002"), \
         patch("backend.api_health.urlopen", side_effect=fake_urlopen):
        snap = stt_provider_health_snapshot()

    assert captured["url"].endswith("/health")
    assert snap["health_url"] == "http://stt:8002/health"


# ---------------------------------------------------------------------------
# stt_provider_health_snapshot — connection failure
# ---------------------------------------------------------------------------

def test_snapshot_streaming_unreachable_on_url_error():
    with patch("backend.api_health.get_stt_provider", return_value="streaming"), \
         patch("backend.api_health.get_stt_provider_url", return_value="http://stt:8002"), \
         patch("backend.api_health.get_stt_provider_ws_url", return_value="ws://stt:8002"), \
         patch("backend.api_health.urlopen", side_effect=URLError("refused")):
        snap = stt_provider_health_snapshot()

    assert snap["reachable"] is False
    assert snap["error"] == "URLError"
    assert snap["latency_ms"] is not None


def test_snapshot_streaming_unreachable_on_os_error():
    with patch("backend.api_health.get_stt_provider", return_value="streaming"), \
         patch("backend.api_health.get_stt_provider_url", return_value="http://stt:8002"), \
         patch("backend.api_health.get_stt_provider_ws_url", return_value="ws://stt:8002"), \
         patch("backend.api_health.urlopen", side_effect=OSError("no route")):
        snap = stt_provider_health_snapshot()

    assert snap["reachable"] is False
    assert snap["error"] == "OSError"


# ---------------------------------------------------------------------------
# stt_provider_health_snapshot — malformed JSON body is handled gracefully
# ---------------------------------------------------------------------------

def test_snapshot_bad_json_body_still_marks_reachable():
    resp = MagicMock()
    resp.status = 200
    resp.read.return_value = b"not-json"
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    with patch("backend.api_health.get_stt_provider", return_value="streaming"), \
         patch("backend.api_health.get_stt_provider_url", return_value="http://stt:8002"), \
         patch("backend.api_health.get_stt_provider_ws_url", return_value="ws://stt:8002"), \
         patch("backend.api_health.urlopen", return_value=resp):
        snap = stt_provider_health_snapshot()

    assert snap["reachable"] is True
    assert "active_connections" not in snap


# ---------------------------------------------------------------------------
# runtime_payload
# ---------------------------------------------------------------------------

def test_runtime_payload_includes_stt_key_with_details():
    with patch("backend.api_health.get_stt_provider", return_value="local"), \
         patch("backend.api_health.get_stt_provider_url", return_value="http://localhost:8000"), \
         patch("backend.api_health.get_stt_provider_ws_url", return_value="ws://localhost:8000"):
        payload = runtime_payload(include_details=True)

    assert "stt_provider" in payload
    assert "models" in payload
    assert "websocket_auth_release" in payload


def test_runtime_payload_excludes_stt_key_without_details():
    payload = runtime_payload(include_details=False)
    assert "stt_provider" not in payload


def test_runtime_payload_degraded_when_streaming_unreachable():
    with patch("backend.api_health.get_stt_provider", return_value="streaming"), \
         patch("backend.api_health.get_stt_provider_url", return_value="http://stt:8002"), \
         patch("backend.api_health.get_stt_provider_ws_url", return_value="ws://stt:8002"), \
         patch("backend.api_health.urlopen", side_effect=OSError("refused")):
        payload = runtime_payload(include_details=True)

    assert payload["ready"] is False
    assert payload["status"] in ("degraded", "warming")


def test_runtime_payload_ready_reflects_runtime_state():
    original = runtime_state.get("ready")
    try:
        runtime_state["ready"] = True
        payload = runtime_payload()
        assert payload.get("ready") is True

        runtime_state["ready"] = False
        payload = runtime_payload()
        assert payload.get("ready") is False
    finally:
        if original is not None:
            runtime_state["ready"] = original
