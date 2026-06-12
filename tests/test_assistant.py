"""Tests for backend/assistant.py and the /api/assistant endpoints."""

import pytest
from unittest.mock import patch, MagicMock

from backend.assistant import _sanitize_message, _frame_message, MAX_MESSAGE_LENGTH


class TestSanitizeMessage:
    def test_strips_control_characters(self):
        assert _sanitize_message("hello\x00world") == "helloworld"
        assert _sanitize_message("test\x08\x0b\x0c\x1f") == "test"

    def test_truncates_long_messages(self):
        long_msg = "a" * (MAX_MESSAGE_LENGTH + 100)
        result = _sanitize_message(long_msg)
        assert len(result) == MAX_MESSAGE_LENGTH

    def test_strips_whitespace(self):
        assert _sanitize_message("  hello  ") == "hello"

    def test_preserves_unicode(self):
        assert _sanitize_message("Hola, ¿cómo estás?") == "Hola, ¿cómo estás?"

    def test_empty_after_strip(self):
        assert _sanitize_message("   ") == ""


class TestFrameMessage:
    def test_no_context(self):
        assert _frame_message("hello", None) == "hello"

    def test_empty_context(self):
        assert _frame_message("hello", {}) == "hello"

    def test_with_source_text(self):
        ctx = {"source_language": "en", "target_language": "es", "source_text": "Hello"}
        result = _frame_message("rephrase it", ctx)
        assert "[translation context]" in result
        assert "en: Hello" in result
        assert "[user] rephrase it" in result

    def test_with_both_texts(self):
        ctx = {
            "source_language": "en",
            "target_language": "es",
            "source_text": "Hello",
            "translated_text": "Hola",
        }
        result = _frame_message("formal?", ctx)
        assert "en: Hello" in result
        assert "es: Hola" in result

    def test_only_translated_text(self):
        ctx = {"source_language": "en", "target_language": "es", "translated_text": "Hola"}
        result = _frame_message("explain", ctx)
        assert "es: Hola" in result
        assert "[user] explain" in result


class TestAssistantAvailability:
    def test_is_available_reflects_import_state(self):
        # The result depends on whether naia deps are installed.
        # We just verify the function runs without error.
        from backend.assistant import is_available, import_error
        assert isinstance(is_available(), bool)
        if not is_available():
            assert import_error() is not None
        else:
            assert import_error() is None

    def test_chat_rejects_empty_message(self):
        import asyncio

        from backend.assistant import chat

        with pytest.raises(ValueError, match="non-empty"):
            asyncio.run(chat(""))


class TestAssistantHttpEndpoints:
    @pytest.fixture()
    def client(self):
        import importlib

        from fastapi.testclient import TestClient

        app_module = importlib.import_module("backend.api")
        return TestClient(app_module.app)

    def test_health_reports_unavailable(self, client, monkeypatch):
        import importlib

        app_module = importlib.import_module("backend.api")
        monkeypatch.setattr(app_module.naia_assistant, "is_available", lambda: False)
        monkeypatch.setattr(app_module.naia_assistant, "import_error", lambda: "ModuleNotFoundError: naia")

        response = client.get("/api/assistant/health")
        assert response.status_code == 200
        body = response.json()
        assert body["available"] is False
        assert "naia" in body["error"]

    def test_health_reports_available(self, client, monkeypatch):
        import importlib

        app_module = importlib.import_module("backend.api")
        monkeypatch.setattr(app_module.naia_assistant, "is_available", lambda: True)

        response = client.get("/api/assistant/health")
        assert response.status_code == 200
        assert response.json()["available"] is True

    def test_chat_requires_message(self, client, monkeypatch):
        import importlib

        app_module = importlib.import_module("backend.api")
        monkeypatch.setattr(app_module.naia_assistant, "is_available", lambda: True)

        response = client.post("/api/assistant/chat", json={"message": "   "})
        assert response.status_code == 400

    def test_chat_unavailable_returns_503(self, client, monkeypatch):
        import importlib

        app_module = importlib.import_module("backend.api")
        monkeypatch.setattr(app_module.naia_assistant, "is_available", lambda: False)
        monkeypatch.setattr(app_module.naia_assistant, "import_error", lambda: "missing")

        response = client.post("/api/assistant/chat", json={"message": "hello"})
        assert response.status_code == 503

    def test_chat_success(self, client, monkeypatch):
        import importlib

        app_module = importlib.import_module("backend.api")

        async def stub_chat(message, *, source="http", translation_context=None, metadata=None):
            return {
                "session_id": "sess-1",
                "response": f"echo:{message}",
                "confidence": 0.9,
                "intent": "statement",
                "task_type": "chat",
                "cognitive_mode": "default",
            }

        monkeypatch.setattr(app_module.naia_assistant, "is_available", lambda: True)
        monkeypatch.setattr(app_module.naia_assistant, "chat", stub_chat)

        response = client.post(
            "/api/assistant/chat",
            json={"message": "hello", "session_id": "mobile-1", "translation_context": {"source_text": "Hi"}},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["response"] == "echo:hello"
        assert body["session_id"] == "sess-1"
