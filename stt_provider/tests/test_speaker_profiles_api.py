"""
Tests for speaker profile API endpoints.

This module contains integration tests for speaker profile management API endpoints,
including enrollment, listing, and deletion of speaker profiles. It verifies that
speaker enrollment is admin-only and that encrypted embeddings are never returned.

Run tests:
    pytest tests/test_speaker_profiles_api.py

Purpose:
This ensures that speaker profile management is properly protected (admin-only access),
that speaker profiles can be enrolled, listed, and deleted, and that encrypted voice
embeddings are never exposed through the API. This supports the guide's Phase 4 speaker
enrollment feature and ensures voice embeddings are treated as biometric data with
encryption, audit logging, and deletion capabilities.
"""
import logging

from uuid import UUID
from typing import Optional

import pytest
from httpx import AsyncClient

logger = logging.getLogger(__name__)


TENANT_ID = "00000000-0000-0000-0000-000000000123"
SPEAKER_ID = "00000000-0000-0000-0000-000000000456"


@pytest.mark.asyncio
async def test_admin_can_enroll_speaker_profile(app):
    """
    Test that admin users can enroll a new speaker profile.
    
    Verifies that users with admin API keys can successfully enroll a speaker profile
    with a display name and consent record ID, and that the response does not include
    the encrypted voice embedding for privacy.
    """
    logger.info("Testing admin can enroll speaker profile")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            f"/v1/admin/tenants/{TENANT_ID}/speaker-profiles",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            data={
                "display_name": "Alex",
                "consent_record_id": "consent_123",
            },
            files={
                "file": ("sample.wav", b"fake-audio", "audio/wav"),
            },
        )

    assert response.status_code in {200, 201}

    body = response.json()

    assert body["display_name"] == "Alex"
    assert body["consent_record_id"] == "consent_123"
    assert body["embedding_model"] == "speaker-embedding-v1"
    assert "encrypted_embedding" not in body  # Privacy: never return raw embeddings
    
    logger.info("Admin speaker profile enrollment test passed")


@pytest.mark.asyncio
async def test_admin_can_list_speaker_profiles(app):
    """
    Test that admin users can list speaker profiles for a tenant.
    
    Verifies that users with admin API keys can list all speaker profiles for a tenant,
    and that the response does not include encrypted voice embeddings for privacy.
    """
    logger.info("Testing admin can list speaker profiles")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            f"/v1/admin/tenants/{TENANT_ID}/speaker-profiles",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["tenant_id"] == TENANT_ID
    assert "speaker_profiles" in body

    # Privacy: ensure encrypted embeddings are not exposed
    for profile in body["speaker_profiles"]:
        assert "encrypted_embedding" not in profile
    
    logger.info("Admin speaker profile listing test passed")


@pytest.mark.asyncio
async def test_admin_can_delete_speaker_profile(app):
    """
    Test that admin users can delete a speaker profile.
    
    Verifies that users with admin API keys can successfully delete a speaker profile,
    and that the response confirms the deletion with the tenant ID and speaker profile ID.
    """
    logger.info("Testing admin can delete speaker profile")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.delete(
            f"/v1/admin/tenants/{TENANT_ID}/speaker-profiles/{SPEAKER_ID}",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": TENANT_ID,
        "speaker_profile_id": SPEAKER_ID,
        "deleted": True,
    }
    
    logger.info("Admin speaker profile deletion test passed")


@pytest.mark.asyncio
async def test_non_admin_cannot_manage_speaker_profiles(app):
    """
    Test that non-admin users cannot access speaker profile management endpoints.
    
    Verifies that users without admin API keys are denied access to speaker profile
    management endpoints with a 403 Forbidden status.
    """
    logger.info("Testing non-admin cannot manage speaker profiles")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            f"/v1/admin/tenants/{TENANT_ID}/speaker-profiles",
            headers={
                "Authorization": "Bearer stream-only-test-key",
            },
        )

    assert response.status_code == 403  # Forbidden
    
    logger.info("Non-admin access rejection test passed")


@pytest.mark.asyncio
async def test_enrollment_requires_display_name(app):
    """
    Test that speaker profile enrollment requires a display name.
    
    Verifies that enrollment requests without a display name are rejected with a
    422 Unprocessable Entity validation error.
    """
    logger.info("Testing enrollment requires display name")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            f"/v1/admin/tenants/{TENANT_ID}/speaker-profiles",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            data={
                "consent_record_id": "consent_123",
                # Missing display_name
            },
            files={
                "file": ("sample.wav", b"fake-audio", "audio/wav"),
            },
        )

    assert response.status_code == 422  # Validation error
    
    logger.info("Display name requirement test passed")


@pytest.mark.asyncio
async def test_enrollment_requires_audio_file(app):
    """
    Test that speaker profile enrollment requires an audio file.
    
    Verifies that enrollment requests without an audio file are rejected with a
    422 Unprocessable Entity validation error.
    """
    logger.info("Testing enrollment requires audio file")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            f"/v1/admin/tenants/{TENANT_ID}/speaker-profiles",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            data={
                "display_name": "Alex",
                "consent_record_id": "consent_123",
            },
            # Missing audio file
        )

    assert response.status_code == 422  # Validation error
    
    logger.info("Audio file requirement test passed")


@pytest.mark.asyncio
async def test_enrollment_requires_authentication(app):
    """
    Test that speaker profile enrollment requires authentication.
    
    Verifies that enrollment requests without an Authorization header are rejected with a
    401 Unauthorized status.
    """
    logger.info("Testing enrollment requires authentication")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            f"/v1/admin/tenants/{TENANT_ID}/speaker-profiles",
            # Missing Authorization header
            data={
                "display_name": "Alex",
                "consent_record_id": "consent_123",
            },
            files={
                "file": ("sample.wav", b"fake-audio", "audio/wav"),
            },
        )

    assert response.status_code == 401  # Unauthorized
    
    logger.info("Authentication requirement test passed")
