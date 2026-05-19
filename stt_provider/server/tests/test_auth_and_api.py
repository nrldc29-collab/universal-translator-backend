"""
Tests for authentication and API functionality.

This module tests authentication mechanisms, API key validation, startup configuration,
batch transcription endpoints, WebSocket streaming, rate limiting, and decoder options.
Tests verify that the API properly validates credentials, enforces rate limits,
handles CORS, and processes transcription requests correctly.

Run tests:
    pytest server/tests/test_auth_and_api.py

Purpose:
This ensures that the STT service's authentication layer and API endpoints work
correctly, including API key validation, rate limiting, CORS enforcement, and
decoder option processing for both batch and streaming transcription.
"""
import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from stt_server import auth, main

logger = logging.getLogger(__name__)

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_TOO_MANY_REQUESTS = 429
WS_POLICY_VIOLATION = 1008


@pytest.fixture(autouse=True)
def configured_app(monkeypatch):
    """
    Configure the FastAPI app for authentication and API testing.
    
    Sets up test configuration including API keys, environment settings,
    and mocks for model warmup and usage tracking. Resets state between
    tests to ensure test isolation.
    """
    logger.info("Configuring app for authentication and API tests")
    
    monkeypatch.setattr(main.settings, "env", "dev")
    monkeypatch.setattr(main.settings, "stt_api_key", "primary-key")
    monkeypatch.setattr(main.settings, "stt_api_keys", "browser:browser-key,cli:cli-key")
    monkeypatch.setattr(main.settings, "allowed_origins", "http://allowed.test")
    monkeypatch.setattr(main, "warmup_model", lambda: None)
    monkeypatch.setattr(main.usage_store, "load", lambda: None)
    monkeypatch.setattr(main.usage_store, "save", lambda: None)

    main.active_connections = 0
    main.active_connections_by_key_label.clear()
    main.usage_store.by_key_label.clear()
    main.limiter._storage.reset()

    yield

    main.active_connections = 0
    main.active_connections_by_key_label.clear()
    main.usage_store.by_key_label.clear()
    main.limiter._storage.reset()
    
    logger.info("App configuration cleaned up")


def test_auth_accepts_primary_and_labeled_keys():
    """
    Test that authentication accepts primary and labeled API keys.
    
    Verifies that the authentication module correctly validates the primary
    API key and labeled API keys (browser, cli), and rejects unknown keys.
    Also verifies that API key labels are correctly extracted.
    """
    logger.info("Testing authentication accepts primary and labeled API keys")
    
    assert auth.is_valid_api_key("primary-key")
    assert auth.is_valid_api_key("browser-key")
    assert auth.is_valid_api_key("cli-key")
    assert not auth.is_valid_api_key("unknown-key")

    assert auth.api_key_label("primary-key") == "default"
    assert auth.api_key_label("browser-key") == "browser"
    assert auth.api_key_label("cli-key") == "cli"
    
    logger.info("Authentication acceptance test passed")


def test_startup_allows_empty_api_key_in_dev(monkeypatch):
    """
    Test that startup allows empty API key in dev environment.
    
    Verifies that in development mode, the service can start with an empty
    API key configuration for testing purposes.
    """
    logger.info("Testing startup allows empty API key in dev environment")
    
    monkeypatch.setattr(main.settings, "env", "dev")
    monkeypatch.setattr(main.settings, "stt_api_key", "")

    main.validate_startup_config()
    
    logger.info("Empty API key in dev test passed")


def test_startup_rejects_empty_api_key_outside_dev(monkeypatch):
    """
    Test that startup rejects empty API key outside dev environment.
    
    Verifies that in non-development environments, the service requires
    an explicitly configured API key and raises an error if missing.
    """
    logger.info("Testing startup rejects empty API key outside dev environment")
    
    monkeypatch.setattr(main.settings, "env", "staging")
    monkeypatch.setattr(main.settings, "stt_api_key", "")

    with pytest.raises(RuntimeError, match="STT_API_KEY must be explicitly configured"):
        main.validate_startup_config()
    
    logger.info("Empty API key rejection outside dev test passed")


def test_build_decoder_options_strips_hotwords_and_drops_empty_values():
    """
    Test that decoder options builder strips hotwords and drops empty values.
    
    Verifies that the decoder options builder properly cleans hotword strings,
    removes empty values, and preserves valid decoder configuration options.
    """
    logger.info("Testing decoder options builder strips hotwords and drops empty values")
    
    assert main.build_decoder_options(
        hotwords=" alpha, beta ,, gamma ",
        initial_prompt="start here",
        beam_size=3,
        word_timestamps=True,
        temperature=0.2,
    ) == {
        "hotwords": ["alpha", "beta", "gamma"],
        "initial_prompt": "start here",
        "beam_size": 3,
        "word_timestamps": True,
        "temperature": 0.2,
    }

    assert main.build_decoder_options() == {}
    
    logger.info("Decoder options builder test passed")


def test_http_trace_id_header_uses_incoming_value():
    """
    Test that HTTP trace ID header uses incoming value.
    
    Verifies that when a client provides an x-trace-id header, the service
    echoes it back in the response for distributed tracing.
    """
    logger.info("Testing HTTP trace ID header uses incoming value")
    
    response = TestClient(main.app).get(
        "/health",
        headers={"x-trace-id": "trace-from-client"},
    )

    assert response.status_code == HTTP_OK
    assert response.headers["x-trace-id"] == "trace-from-client"
    
    logger.info("HTTP trace ID header test passed")


def test_http_trace_id_header_is_generated():
    """
    Test that HTTP trace ID header is generated when not provided.
    
    Verifies that when no trace ID is provided, the service generates
    a valid UUID and returns it in the response headers.
    """
    logger.info("Testing HTTP trace ID header is generated")
    
    response = TestClient(main.app).get("/health")

    assert response.status_code == HTTP_OK
    uuid.UUID(response.headers["x-trace-id"])
    
    logger.info("HTTP trace ID generation test passed")


def test_batch_transcription_accepts_labeled_api_key(monkeypatch):
    """
    Test that batch transcription accepts labeled API keys.
    
    Verifies that the batch transcription endpoint accepts labeled API keys
    (e.g., cli-key) and processes transcription requests correctly.
    """
    logger.info("Testing batch transcription accepts labeled API key")
    
    monkeypatch.setattr(
        main,
        "transcribe_pcm16_file",
        lambda path, language_override=None: f"transcribed:{language_override}",
    )

    response = TestClient(main.app).post(
        "/v1/audio/transcriptions",
        headers={"Authorization": "Bearer cli-key"},
        data={"model": "base", "language": "en"},
        files={"file": ("sample.wav", b"not-a-real-wav", "audio/wav")},
    )

    assert response.status_code == HTTP_OK
    assert response.json()["text"] == "transcribed:en"
    
    logger.info("Batch transcription labeled API key test passed")


def test_batch_transcription_forwards_decoder_options(monkeypatch):
    """
    Test that batch transcription forwards decoder options.
    
    Verifies that decoder options (hotwords, initial_prompt, beam_size,
    word_timestamps, temperature) are correctly parsed and forwarded
    to the transcription function.
    """
    logger.info("Testing batch transcription forwards decoder options")
    
    captured = {}

    def fake_transcribe(path, language_override=None, **decoder_options):
        captured["language_override"] = language_override
        captured["decoder_options"] = decoder_options
        return "transcribed"

    monkeypatch.setattr(main, "transcribe_pcm16_file", fake_transcribe)

    response = TestClient(main.app).post(
        "/v1/audio/transcriptions",
        headers={"Authorization": "Bearer cli-key"},
        data={
            "model": "base",
            "language": "en",
            "hotwords": "alpha,beta",
            "initial_prompt": "start here",
            "beam_size": "4",
            "word_timestamps": "true",
            "temperature": "0.25",
        },
        files={"file": ("sample.wav", b"not-a-real-wav", "audio/wav")},
    )

    assert response.status_code == HTTP_OK
    assert captured == {
        "language_override": "en",
        "decoder_options": {
            "hotwords": ["alpha", "beta"],
            "initial_prompt": "start here",
            "beam_size": 4,
            "word_timestamps": True,
            "temperature": 0.25,
        },
    }
    
    logger.info("Batch transcription decoder options test passed")


def test_batch_transcription_rate_limit_uses_api_key(monkeypatch):
    """
    Test that batch transcription rate limit uses API key.
    
    Verifies that rate limiting is enforced per API key, and that
    requests beyond the limit are rejected with 429 status.
    """
    logger.info("Testing batch transcription rate limit uses API key")
    
    monkeypatch.setattr(main, "transcribe_pcm16_file", lambda *args, **kwargs: "ok")
    client = TestClient(main.app)

    for _ in range(30):
        response = client.post(
            "/v1/audio/transcriptions",
            headers={"Authorization": "Bearer cli-key"},
            data={"model": "base", "language": "en"},
            files={"file": ("sample.wav", b"not-a-real-wav", "audio/wav")},
        )
        assert response.status_code == HTTP_OK

    response = client.post(
        "/v1/audio/transcriptions",
        headers={"Authorization": "Bearer cli-key"},
        data={"model": "base", "language": "en"},
        files={"file": ("sample.wav", b"not-a-real-wav", "audio/wav")},
    )

    assert response.status_code == HTTP_TOO_MANY_REQUESTS
    
    logger.info("Batch transcription rate limit test passed")


def test_batch_transcription_rejects_unknown_api_key(monkeypatch):
    """
    Test that batch transcription rejects unknown API key.
    
    Verifies that transcription requests with invalid API keys are
    rejected before any transcription processing occurs.
    """
    logger.info("Testing batch transcription rejects unknown API key")
    
    def fail_if_called(path, language_override=None):
        raise AssertionError("transcription should not run for an invalid key")

    monkeypatch.setattr(main, "transcribe_pcm16_file", fail_if_called)

    response = TestClient(main.app).post(
        "/v1/audio/transcriptions",
        headers={"Authorization": "Bearer bad-key"},
        data={"model": "base", "language": "en"},
        files={"file": ("sample.wav", b"not-a-real-wav", "audio/wav")},
    )

    assert response.status_code == HTTP_UNAUTHORIZED
    
    logger.info("Batch transcription unknown API key rejection test passed")


def test_usage_reset_rate_limit_uses_admin_api_key(monkeypatch):
    """
    Test that usage reset rate limit uses admin API key.
    
    Verifies that the admin usage reset endpoint is rate limited per
    admin API key, and requests beyond the limit are rejected.
    """
    logger.info("Testing usage reset rate limit uses admin API key")
    
    monkeypatch.setattr(main.settings, "enable_admin_reset", True)
    monkeypatch.setattr(main.settings, "admin_api_key", "admin-key")
    monkeypatch.setattr(main.usage_store, "reset", lambda: None)
    monkeypatch.setattr(main.metrics, "restore_from_usage_store", lambda: None)
    monkeypatch.setattr(main, "log_admin_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "log_event", lambda *args, **kwargs: None)
    client = TestClient(main.app)

    for _ in range(5):
        response = client.post(
            "/v1/usage/reset",
            headers={"Authorization": "Bearer admin-key"},
        )
        assert response.status_code == HTTP_OK

    response = client.post(
        "/v1/usage/reset",
        headers={"Authorization": "Bearer admin-key"},
    )

    assert response.status_code == HTTP_TOO_MANY_REQUESTS
    
    logger.info("Usage reset rate limit test passed")


def test_websocket_allows_non_browser_clients_without_origin():
    """
    Test that WebSocket allows non-browser clients without origin.
    
    Verifies that WebSocket connections without an origin header
    (typically non-browser clients) are accepted with valid API keys.
    """
    logger.info("Testing WebSocket allows non-browser clients without origin")
    
    with TestClient(main.app).websocket_connect("/stt/stream?api_key=primary-key") as websocket:
        event = websocket.receive_json()

    assert event["type"] == "session.started"
    uuid.UUID(event["trace_id"])
    
    logger.info("WebSocket non-browser client test passed")


def test_websocket_rejects_disallowed_browser_origin():
    """
    Test that WebSocket rejects disallowed browser origin.
    
    Verifies that WebSocket connections from disallowed origins
    are rejected with a policy violation close code.
    """
    logger.info("Testing WebSocket rejects disallowed browser origin")
    
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with TestClient(main.app).websocket_connect(
            "/stt/stream?api_key=primary-key",
            headers={"origin": "http://blocked.test"},
        ):
            pass

    assert exc_info.value.code == WS_POLICY_VIOLATION
    
    logger.info("WebSocket disallowed origin rejection test passed")


def test_websocket_forwards_decoder_options(monkeypatch):
    """
    Test that WebSocket forwards decoder options.
    
    Verifies that decoder options passed via query parameters are
    correctly parsed and forwarded to the streaming session.
    """
    logger.info("Testing WebSocket forwards decoder options")
    
    captured = {}

    class FakeSession:
        def __init__(self, language=None, decoder_options=None):
            captured["language"] = language
            captured["decoder_options"] = decoder_options

        async def flush(self):
            if False:
                yield None

    monkeypatch.setattr(main, "StreamingTranscriptionSession", FakeSession)

    with TestClient(main.app).websocket_connect(
        "/stt/stream?"
        "api_key=primary-key&"
        "language=en&"
        "hotwords=alpha,beta&"
        "initial_prompt=start%20here&"
        "beam_size=4&"
        "word_timestamps=true&"
        "temperature=0.25"
    ) as websocket:
        event = websocket.receive_json()

    assert event["type"] == "session.started"
    assert captured == {
        "language": "en",
        "decoder_options": {
            "hotwords": ["alpha", "beta"],
            "initial_prompt": "start here",
            "beam_size": 4,
            "word_timestamps": True,
            "temperature": 0.25,
        },
    }
    
    logger.info("WebSocket decoder options test passed")
