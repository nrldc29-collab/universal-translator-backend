"""Tests for backend.stt_bridge — STTBridge._check_streaming_health."""

from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from backend.stt_bridge import STTBridge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_streaming_bridge():
    with patch("backend.stt_bridge.get_stt_provider", return_value="streaming"), \
         patch("backend.stt_bridge.get_stt_provider_url", return_value="http://stt:8002"), \
         patch("backend.stt_bridge.get_stt_provider_ws_url", return_value="ws://stt:8002"), \
         patch("backend.stt_bridge.get_stt_provider_api_key", return_value="test-key"):
        return STTBridge()


def _mock_urlopen_ok():
    resp = MagicMock()
    resp.status = 200
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# _check_streaming_health — success
# ---------------------------------------------------------------------------

def test_check_streaming_health_returns_true_on_200():
    bridge = _make_streaming_bridge()
    with patch("backend.stt_bridge.get_stt_provider_url", return_value="http://stt:8002"), \
         patch("urllib.request.urlopen", return_value=_mock_urlopen_ok()):
        result = bridge._check_streaming_health()
    assert result is True


def test_check_streaming_health_uses_health_live_endpoint():
    bridge = _make_streaming_bridge()
    captured = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        return _mock_urlopen_ok()

    with patch("backend.stt_bridge.get_stt_provider_url", return_value="http://stt:8002"), \
         patch("urllib.request.urlopen", side_effect=fake_urlopen):
        bridge._check_streaming_health()

    assert captured["url"] == "http://stt:8002/health/live"


# ---------------------------------------------------------------------------
# _check_streaming_health — failure paths
# ---------------------------------------------------------------------------

def test_check_streaming_health_returns_false_on_url_error():
    bridge = _make_streaming_bridge()
    with patch("backend.stt_bridge.get_stt_provider_url", return_value="http://stt:8002"), \
         patch("urllib.request.urlopen", side_effect=URLError("connection refused")):
        result = bridge._check_streaming_health()
    assert result is False


def test_check_streaming_health_returns_false_on_os_error():
    bridge = _make_streaming_bridge()
    with patch("backend.stt_bridge.get_stt_provider_url", return_value="http://stt:8002"), \
         patch("urllib.request.urlopen", side_effect=OSError("no route to host")):
        result = bridge._check_streaming_health()
    assert result is False


def test_check_streaming_health_returns_false_on_timeout():
    bridge = _make_streaming_bridge()
    with patch("backend.stt_bridge.get_stt_provider_url", return_value="http://stt:8002"), \
         patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        result = bridge._check_streaming_health()
    assert result is False


def test_check_streaming_health_returns_false_on_non_200():
    resp = MagicMock()
    resp.status = 503
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    bridge = _make_streaming_bridge()
    with patch("backend.stt_bridge.get_stt_provider_url", return_value="http://stt:8002"), \
         patch("urllib.request.urlopen", return_value=resp):
        result = bridge._check_streaming_health()
    assert result is False


# ---------------------------------------------------------------------------
# is_streaming property
# ---------------------------------------------------------------------------

def test_is_streaming_true_for_streaming_provider():
    bridge = _make_streaming_bridge()
    with patch("backend.stt_bridge.get_stt_provider", return_value="streaming"):
        assert bridge.is_streaming is True


def test_is_streaming_false_for_local_provider():
    with patch("backend.stt_bridge.get_stt_provider", return_value="local"):
        bridge = STTBridge()
    with patch("backend.stt_bridge.get_stt_provider", return_value="local"):
        assert bridge.is_streaming is False
