"""
Tests for request-level model override functionality.

This module tests the ability to override the default STT model on a per-request
basis, ensuring that model overrides are properly authorized and validated.
Tests verify that admin-scoped keys can override models, non-admin keys cannot,
and unknown model IDs are rejected.

Run tests:
    pytest tests/test_model_override.py

Purpose:
This verifies that request-level model overrides are allowed only for admin-scoped
keys and that unsupported model IDs are rejected before traffic can route to an
unloaded Triton model. The guide's domain-model step calls for per-tenant default
model selection and request-level overrides when permitted.
"""
import logging

import pytest
from httpx import AsyncClient

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_admin_can_override_model_on_rest_transcription(app):
    """
    Test that admin-scoped keys can override the model on REST transcription.
    
    Verifies that requests with admin authorization can specify a custom model
    via the model parameter and the request is accepted.
    
    Args:
        app: FastAPI application fixture
    """
    logger.info("Testing admin model override on REST transcription")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/audio/transcriptions",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            files={
                "file": ("sample.wav", b"fake-audio", "audio/wav"),
            },
            data={
                "model": "parakeet-medical",
            },
        )

    logger.info(f"Response status: {response.status_code}")
    assert response.status_code in {200, 202}
    logger.info("Admin model override test passed")


@pytest.mark.asyncio
async def test_non_admin_cannot_override_model_on_rest_transcription(app):
    """
    Test that non-admin keys cannot override the model on REST transcription.
    
    Verifies that requests with non-admin authorization are rejected when
    attempting to override the default model.
    
    Args:
        app: FastAPI application fixture
    """
    logger.info("Testing non-admin model override rejection on REST transcription")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/audio/transcriptions",
            headers={
                "Authorization": "Bearer transcribe-only-test-key",
            },
            files={
                "file": ("sample.wav", b"fake-audio", "audio/wav"),
            },
            data={
                "model": "parakeet-medical",
            },
        )

    logger.info(f"Response status: {response.status_code}")
    assert response.status_code == 403
    logger.info("Non-admin model override rejection test passed")


@pytest.mark.asyncio
async def test_rejects_unknown_model_override_on_rest_transcription(app):
    """
    Test that unknown model IDs are rejected on REST transcription.
    
    Verifies that requests specifying an unknown or unsupported model ID are
    rejected with appropriate error status codes before routing to backend.
    
    Args:
        app: FastAPI application fixture
    """
    logger.info("Testing unknown model ID rejection on REST transcription")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/audio/transcriptions",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            files={
                "file": ("sample.wav", b"fake-audio", "audio/wav"),
            },
            data={
                "model": "unknown-model",
            },
        )

    logger.info(f"Response status: {response.status_code}")
    assert response.status_code in {400, 422}
    logger.info("Unknown model ID rejection test passed")
