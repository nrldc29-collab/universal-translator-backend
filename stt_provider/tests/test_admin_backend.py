"""
Tests for admin backend management API.

This module tests the admin API endpoints for managing tenant backend configurations.
Tests verify that admins can update tenant backends, invalid backend names are rejected,
and non-admin API keys cannot modify backend configurations.

Run tests:
    pytest tests/test_admin_backend.py

Purpose:
This ensures that the admin backend management API properly enforces authorization,
validates backend names, and allows safe tenant backend configuration for Phase 2B rollout.
"""
import logging

import pytest
from httpx import AsyncClient

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_admin_can_update_tenant_backend(app):
    """
    Test that admin can update tenant backend configuration.
    
    Verifies that users with admin API keys can successfully update a tenant's
    backend configuration (e.g., switching between triton and whisper) and
    enable or disable backend fallback.
    """
    logger.info("Testing admin can update tenant backend configuration")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.put(
            "/v1/admin/tenants/tenant_123/backend",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            json={
                "backend": "triton",
                "allow_backend_fallback": True,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": "tenant_123",
        "backend": "triton",
        "allow_backend_fallback": True,
    }
    
    logger.info("Admin tenant backend update test passed")


@pytest.mark.asyncio
async def test_rejects_invalid_backend(app):
    """
    Test that invalid backend names are rejected.
    
    Verifies that the API rejects requests with invalid backend names (e.g., 'deepgram')
    that are not supported by the system, returning a 422 Unprocessable Entity status.
    """
    logger.info("Testing invalid backend name rejection")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.put(
            "/v1/admin/tenants/tenant_123/backend",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            json={
                "backend": "deepgram",
                "allow_backend_fallback": True,
            },
        )

    assert response.status_code == 422
    
    logger.info("Invalid backend rejection test passed")


@pytest.mark.asyncio
async def test_non_admin_key_cannot_update_tenant_backend(app):
    """
    Test that non-admin keys cannot update tenant backend.
    
    Verifies that API keys without admin privileges are forbidden from modifying
    tenant backend configurations, returning a 403 Forbidden status.
    """
    logger.info("Testing non-admin key cannot update tenant backend")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.put(
            "/v1/admin/tenants/tenant_123/backend",
            headers={
                "Authorization": "Bearer stream-only-test-key",
            },
            json={
                "backend": "whisper",
                "allow_backend_fallback": True,
            },
        )

    assert response.status_code == 403
    
    logger.info("Non-admin key rejection test passed")
