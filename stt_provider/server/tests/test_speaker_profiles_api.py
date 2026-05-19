"""
Tests for speaker profiles API functionality.

This module tests the speaker profiles API endpoints which manage speaker
enrollment and profile operations. Tests verify authentication requirements,
profile creation, listing, deletion, and display name validation.

Run tests:
    pytest server/tests/test_speaker_profiles_api.py

Purpose:
This ensures that the speaker profiles API properly enforces authentication,
validates input, and handles profile CRUD operations securely and correctly.
"""
import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile

from stt_server import main
from stt_server.speaker_profiles_api import router as speaker_profiles_router

logger = logging.getLogger(__name__)

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_BAD_REQUEST = 400


@pytest.fixture(autouse=True)
def configured_app(monkeypatch):
    """
    Configure the FastAPI app for speaker profiles API testing.
    
    Sets up test configuration including API keys, environment settings,
    and mocks for model warmup and usage tracking. Resets state between
    tests to ensure test isolation.
    """
    logger.info("Configuring app for speaker profiles API tests")
    
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


def test_speaker_profile_creation_requires_authentication():
    """
    Test that creating a speaker profile requires valid API key.
    
    Verifies that profile creation requests with invalid or missing
    authentication are rejected with a 401 Unauthorized status.
    """
    logger.info("Testing speaker profile creation requires authentication")
    
    client = TestClient(main.app)
    
    # Create a fake audio file
    fake_audio = b"fake audio data"
    
    response = client.post(
        "/v1/speaker-profiles",
        headers={"Authorization": "Bearer invalid-key"},
        data={
            "display_name": "Test User",
            "file": ("test.wav", fake_audio, "audio/wav"),
        },
    )
    
    assert response.status_code == HTTP_UNAUTHORIZED
    
    logger.info("Speaker profile creation authentication test passed")


def test_speaker_profile_creation_with_valid_api_key(monkeypatch):
    """
    Test that creating a speaker profile works with valid API key.
    
    Verifies that profile creation requests with valid authentication
    succeed and return an appropriate success status code.
    """
    logger.info("Testing speaker profile creation with valid API key")
    
    # Mock the database operations
    async def mock_fetch(*args, **kwargs):
        return []
    
    async def mock_execute(*args, **kwargs):
        return None
    
    monkeypatch.setattr("stt_server.speaker_profiles_api.db.fetch", mock_fetch)
    monkeypatch.setattr("stt_server.speaker_profiles_api.db.execute", mock_execute)
    
    client = TestClient(main.app)
    
    # Create a fake audio file
    fake_audio = b"fake audio data"
    
    response = client.post(
        "/v1/speaker-profiles",
        headers={"Authorization": "Bearer primary-key"},
        data={
            "display_name": "Test User",
            "file": ("test.wav", fake_audio, "audio/wav"),
        },
    )
    
    # Should return 200 or 201 on success
    assert response.status_code in (HTTP_OK, 201)
    
    logger.info("Speaker profile creation with valid API key test passed")


def test_speaker_profile_listing_requires_authentication():
    """
    Test that listing speaker profiles requires valid API key.
    
    Verifies that profile listing requests with invalid or missing
    authentication are rejected with a 401 Unauthorized status.
    """
    logger.info("Testing speaker profile listing requires authentication")
    
    client = TestClient(main.app)
    
    response = client.get(
        "/v1/speaker-profiles",
        headers={"Authorization": "Bearer invalid-key"},
    )
    
    assert response.status_code == HTTP_UNAUTHORIZED
    
    logger.info("Speaker profile listing authentication test passed")


def test_speaker_profile_deletion_requires_authentication():
    """
    Test that deleting a speaker profile requires valid API key.
    
    Verifies that profile deletion requests with invalid or missing
    authentication are rejected with a 401 Unauthorized status.
    """
    logger.info("Testing speaker profile deletion requires authentication")
    
    client = TestClient(main.app)
    profile_id = str(uuid.uuid4())
    
    response = client.delete(
        f"/v1/speaker-profiles/{profile_id}",
        headers={"Authorization": "Bearer invalid-key"},
    )
    
    assert response.status_code == HTTP_UNAUTHORIZED
    
    logger.info("Speaker profile deletion authentication test passed")


def test_speaker_profile_display_name_validation():
    """
    Test that display name validation works.
    
    Verifies that profile creation requests with empty display names
    are rejected with a 400 Bad Request status.
    """
    logger.info("Testing speaker profile display name validation")
    
    client = TestClient(main.app)
    
    # Test empty display name
    response = client.post(
        "/v1/speaker-profiles",
        headers={"Authorization": "Bearer primary-key"},
        data={
            "display_name": "",
            "file": ("test.wav", b"fake audio", "audio/wav"),
        },
    )
    
    assert response.status_code == HTTP_BAD_REQUEST
    
    logger.info("Speaker profile display name validation test passed")
