"""HTTP integration tests for core translation and TTS endpoints."""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def app_module():
    return importlib.import_module("backend.api")


@pytest.fixture()
def client(app_module):
    return TestClient(app_module.app)


@pytest.fixture(autouse=True)
def stub_pipeline(app_module, monkeypatch, tmp_path):
    from backend.pipeline import TranslationResult

    def stub_translate_text(text, source_language, target_language, **kwargs):
        return TranslationResult(
            source_text=text,
            improved_text=text,
            translated_text="hola" if target_language == "es" else text,
            audio_output_path=None,
        )

    def stub_synthesize(text, output_path, language="en", **kwargs):
        path = tmp_path / f"{language}.wav"
        path.write_bytes(b"RIFF" + b"\x00" * 96)
        return str(path)

    monkeypatch.setattr(app_module.pipeline, "translate_text", stub_translate_text)
    monkeypatch.setattr(app_module.pipeline.tts, "synthesize", stub_synthesize)


class TestTranslateText:
    def test_translate_en_to_es(self, client):
        response = client.post(
            "/translate/text",
            json={
                "text": "hello",
                "source_language": "en",
                "target_language": "es",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert "hola" in payload["translated_text"].lower()

    def test_translate_ht_to_en(self, client):
        response = client.post(
            "/translate/text",
            json={
                "text": "M ap byen",
                "source_language": "ht",
                "target_language": "en",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        translated = str(payload.get("translated_text") or "")
        assert translated.strip()
        assert not (translated.startswith("[") and "->" in translated[:12])

    def test_translate_with_session_does_not_block_streams(self, app_module, client):
        app_module.session_registry.cleanup()
        for session_id in ("smoke-a", "smoke-b", "smoke-c"):
            response = client.post(
                "/translate/text",
                json={
                    "text": "hello",
                    "source_language": "en",
                    "target_language": "es",
                    "session_id": session_id,
                },
            )
            assert response.status_code == 200
        assert app_module.session_registry.active_stream_count("dev") == 0


class TestTts:
    def test_tts_en(self, client):
        response = client.post("/tts", json={"text": "hello", "language": "en"})
        assert response.status_code == 200
        payload = response.json()
        assert payload.get("audio_base64") or payload.get("audio_url")

    def test_tts_ht(self, client):
        response = client.post("/tts", json={"text": "Bonjou", "language": "ht"})
        assert response.status_code == 200
        payload = response.json()
        assert payload.get("audio_base64") or payload.get("audio_url")

    def test_translate_text_respects_explicit_direction(self, app_module, client, monkeypatch):
        from backend.pipeline import TranslationResult

        captured = []

        def capture_translate(text, source_language, target_language, **kwargs):
            captured.append((source_language, target_language))
            return TranslationResult(
                source_text=text,
                improved_text=text,
                translated_text="I need help",
                audio_output_path=None,
            )

        monkeypatch.setattr(app_module.pipeline, "translate_text", capture_translate)
        response = client.post(
            "/translate/text",
            json={
                "text": "Mwen bezwen èd",
                "source_language": "en",
                "target_language": "ht",
            },
        )
        assert response.status_code == 200
        assert captured == [("en", "ht")]

    def test_translate_text_survives_tts_failure(self, app_module, client, monkeypatch):
        def fail_cached(*args, **kwargs):
            raise RuntimeError("tts unavailable")

        monkeypatch.setattr(app_module, "_cached_tts_payload", fail_cached)
        response = client.post(
            "/translate/text",
            json={
                "text": "hello",
                "source_language": "en",
                "target_language": "es",
                "synthesize_audio": True,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert "hola" in payload["translated_text"].lower()
        assert not payload.get("audio_base64")
