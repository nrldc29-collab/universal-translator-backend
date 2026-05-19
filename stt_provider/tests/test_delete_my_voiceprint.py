"""
Tests for delete-my-voiceprint functionality.

This module tests the ability for users to delete their own speaker profile
voiceprints, ensuring proper authentication and that biometric embedding data
is never returned in responses. This is a privacy requirement for speaker
enrollment since voice embeddings are biometric data.

Run tests:
    pytest tests/test_delete_my_voiceprint.py

Purpose:
This verifies the delete-my-voiceprint behavior required for speaker enrollment:
authenticated deletion works, unauthenticated deletion is blocked, and biometric
embedding data is never returned. The guide says speaker enrollment must include
a delete-my-voiceprint API because voice embeddings are biometric data that must
be encrypted and deletable.
"""
import logging

from uuid import UUID

import pytest
from httpx import AsyncClient

logger = logging.getLogger(__name__)

SPEAKER_ID = "00000000-0000-0000-0000-000000000456"


@pytest.mark.asyncio
async def test_user_can_delete_own_voiceprint(app):
    """
    Test that authenticated users can delete their own voiceprint.
    
    Verifies that a user with proper authorization can successfully delete
    their speaker profile voiceprint and receive confirmation of deletion.
    
    Args:
        app: FastAPI application fixture
    """
    logger.info(f"Testing voiceprint deletion for speaker ID: {SPEAKER_ID}")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.delete(
            f"/v1/me/speaker-profiles/{SPEAKER_ID}",
            headers={
                "Authorization": "Bearer speaker-owner-test-key",
            },
        )

    logger.info(f"Response status: {response.status_code}")
    assert response.status_code == 200
    assert response.json()["speaker_profile_id"] == SPEAKER_ID
    assert response.json()["deleted"] is True
    logger.info("Voiceprint deletion test passed")


@pytest.mark.asyncio
async def test_delete_my_voiceprint_requires_authentication(app):
    """
    Test that voiceprint deletion requires authentication.
    
    Verifies that unauthenticated requests to delete a voiceprint are
    rejected with appropriate error status codes.
    
    Args:
        app: FastAPI application fixture
    """
    logger.info("Testing voiceprint deletion without authentication")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.delete(
            f"/v1/me/speaker-profiles/{SPEAKER_ID}",
        )

    logger.info(f"Response status: {response.status_code}")
    assert response.status_code in {401, 403}
    logger.info("Authentication requirement test passed")


@pytest.mark.asyncio
async def test_delete_my_voiceprint_does_not_return_embedding(app):
    """
    Test that voiceprint deletion does not return embedding data.
    
    Verifies that the delete response never includes biometric embedding
    data, ensuring privacy protection for voice fingerprints.
    
    Args:
        app: FastAPI application fixture
    """
    logger.info("Testing that deletion response does not include embedding data")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.delete(
            f"/v1/me/speaker-profiles/{SPEAKER_ID}",
            headers={
                "Authorization": "Bearer speaker-owner-test-key",
            },
        )

    logger.info(f"Response status: {response.status_code}")
    assert response.status_code == 200
    assert "encrypted_embedding" not in response.json()
    assert "embedding" not in response.json()
    logger.info("Embedding data exclusion test passed")
