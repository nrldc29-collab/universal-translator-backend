"""WebSocket-level integration tests for the FastAPI backend.

These exercise the actual FastAPI app via Starlette's TestClient, hitting
the real /ws/* routes. They monkeypatch the heavy pieces (translation
pipeline, naia assistant) so the tests don't require model weights, but
the WebSocket protocol itself — accept, message framing, ping/pong,
error handling, close codes — runs unchanged.

Coverage goal: every WebSocket endpoint exposed by backend/api.py at
least has a smoke test that connects, exchanges a message, and closes
cleanly.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def app_module():
    """Import backend.api once; tests may monkeypatch attributes on it."""

    return importlib.import_module("backend.api")


@pytest.fixture()
def client(app_module):
    """Fresh TestClient per test. Lifespan is NOT triggered; tests must
    not depend on model warmup."""

    return TestClient(app_module.app)


# ---------------------------------------------------------------------------
# /ws/ping
# ---------------------------------------------------------------------------


class TestWsPing:
    def test_connects_and_sends_ready(self, client):
        with client.websocket_connect("/ws/ping") as ws:
            message = ws.receive_json()
        assert message["type"] == "ready"
        assert "release" in message
        assert "websocket_auth_release" in message

    def test_server_closes_after_ready(self, client):
        from starlette.websockets import WebSocketDisconnect

        with client.websocket_connect("/ws/ping") as ws:
            ws.receive_json()
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()


# ---------------------------------------------------------------------------
# /ws/translate
# ---------------------------------------------------------------------------


class TestWsTranslate:
    @pytest.fixture(autouse=True)
    def stub_pipeline(self, app_module, monkeypatch):
        from backend.pipeline import TranslationResult

        def stub_translate_text(text, source_language, target_language, **kwargs):
            return TranslationResult(
                source_text=text,
                improved_text=text,
                translated_text=f"[{target_language}] {text}",
                audio_output_path=None,
            )

        monkeypatch.setattr(app_module.pipeline, "translate_text", stub_translate_text)

    def test_ready_frame_on_connect(self, client):
        with client.websocket_connect("/ws/translate") as ws:
            ready = ws.receive_json()
        assert ready["type"] == "ready"
        assert "message" in ready

    def test_ping_returns_pong(self, client):
        with client.websocket_connect("/ws/translate") as ws:
            ws.receive_json()
            ws.send_json({"type": "ping"})
            reply = ws.receive_json()
        assert reply == {"type": "pong"}

    def test_translation_round_trip(self, client):
        with client.websocket_connect("/ws/translate") as ws:
            ws.receive_json()
            ws.send_json({"text": "hello", "source_language": "en", "target_language": "es"})
            reply = ws.receive_json()
        assert reply["type"] == "translation"
        assert reply["source_text"] == "hello"
        assert reply["translated_text"] == "[es] hello"
        assert reply["improved_text"] == "hello"

    def test_empty_text_returns_error(self, client):
        with client.websocket_connect("/ws/translate") as ws:
            ws.receive_json()
            ws.send_json({"text": "   ", "source_language": "en", "target_language": "es"})
            reply = ws.receive_json()
        assert reply["type"] == "error"
        assert "required" in reply["message"].lower()

    def test_defaults_language_when_omitted(self, client):
        with client.websocket_connect("/ws/translate") as ws:
            ws.receive_json()
            ws.send_json({"text": "bonjour"})
            reply = ws.receive_json()
        assert reply["type"] == "translation"
        assert reply["translated_text"] == "[es] bonjour"


# ---------------------------------------------------------------------------
# /ws/audio (auth path smoke test only)
# ---------------------------------------------------------------------------


class TestWsAudio:
    def test_audio_socket_rejects_when_not_ready(self, app_module, client, monkeypatch):
        monkeypatch.setitem(app_module.runtime_state, "ready", False)
        with client.websocket_connect("/ws/audio") as ws:
            payload = ws.receive_json()
        assert payload["type"] == "error"
        assert payload.get("warming") is True
        assert "LIVE" in payload["message"]

    def test_audio_socket_accepts_when_ready(self, app_module, client, monkeypatch):
        monkeypatch.setitem(app_module.runtime_state, "ready", True)
        with client.websocket_connect("/ws/audio") as ws:
            payload = ws.receive_json()
        assert payload["type"] == "ready"


# ---------------------------------------------------------------------------
# /ws/assistant
# ---------------------------------------------------------------------------


class TestWsAssistant:
    def test_unavailable_returns_error_and_closes(self, app_module, client, monkeypatch):
        monkeypatch.setattr(app_module.naia_assistant, "is_available", lambda: False)
        monkeypatch.setattr(
            app_module.naia_assistant,
            "import_error",
            lambda: "naia not installed",
        )

        from starlette.websockets import WebSocketDisconnect

        with client.websocket_connect("/ws/assistant") as ws:
            payload = ws.receive_json()
            assert payload["event"] == "error"
            assert "Assistant unavailable" in payload["detail"]
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()

    def test_available_round_trip(self, app_module, client, monkeypatch):
        async def stub_chat(message, **kwargs):
            return {"text": f"echo: {message}", "metadata": kwargs.get("metadata") or {}}

        monkeypatch.setattr(app_module.naia_assistant, "is_available", lambda: True)
        monkeypatch.setattr(app_module.naia_assistant, "chat", stub_chat)

        with client.websocket_connect("/ws/assistant") as ws:
            ws.send_json({"message": "hello"})
            started = ws.receive_json()
            assert started == {"event": "started"}
            completed = ws.receive_json()
            assert completed["event"] == "completed"
            assert completed["response"]["text"] == "echo: hello"

    def test_empty_message_is_rejected(self, app_module, client, monkeypatch):
        monkeypatch.setattr(app_module.naia_assistant, "is_available", lambda: True)

        with client.websocket_connect("/ws/assistant") as ws:
            ws.send_json({"message": "   "})
            reply = ws.receive_json()
        assert reply["event"] == "error"
        assert "required" in reply["detail"].lower()
