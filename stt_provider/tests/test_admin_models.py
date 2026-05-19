"""
Tests for admin model management API.

This module tests the admin API endpoints for managing tenant default model configurations.
Tests verify that admins can update tenant default models, and unknown model IDs are rejected
to prevent routing traffic to unsupported or unloaded Triton models.

Run tests:
    pytest tests/test_admin_models.py

Purpose:
This ensures that the admin model management API properly validates model IDs and allows
safe tenant default model configuration as part of the Phase 4 self-hosted differentiation path.
"""
import logging

import pytest
from httpx import AsyncClient

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_admin_can_update_tenant_default_model(app):
    """
    Test that admin can update tenant default model.
    
    Verifies that users with admin API keys can successfully update a tenant's
    default domain model (e.g., parakeet-medical) for transcription requests.
    """
    logger.info("Testing admin can update tenant default model")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.put(
            "/v1/admin/tenants/tenant_123/default-model",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            json={
                "default_model_id": "parakeet-medical",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": "tenant_123",
        "default_model_id": "parakeet-medical",
    }
    
    logger.info("Admin tenant default model update test passed")


@pytest.mark.asyncio
async def test_rejects_unknown_tenant_default_model(app):
    """
    Test that unknown model IDs are rejected.
    
    Verifies that the API rejects requests with unknown or unsupported model IDs,
    returning a 422 Unprocessable Entity status with an unsupported_model_id error.
    This prevents routing traffic to unloaded Triton models.
    """
    logger.info("Testing unknown model ID rejection")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.put(
            "/v1/admin/tenants/tenant_123/default-model",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            json={
                "default_model_id": "unknown-model",
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "unsupported_model_id"
    
    logger.info("Unknown model ID rejection test passed")
