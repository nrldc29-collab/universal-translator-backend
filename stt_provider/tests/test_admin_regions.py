"""
Tests for admin region management API.

This module tests the admin API endpoints for managing tenant region configurations.
Tests verify that admins can update tenant home regions, unsupported regions are rejected,
and non-admin API keys cannot modify region configurations. Region routing is critical
for data-residency compliance and regional GPU capacity management.

Run tests:
    pytest tests/test_admin_regions.py

Purpose:
This ensures that the admin region management API properly enforces authorization,
validates region names, and allows safe tenant region configuration for co-located GPU
regions, data-residency policy compliance, and regional failover behavior.
"""
import logging

import pytest
from httpx import AsyncClient

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_admin_can_update_tenant_region(app):
    """
    Test that admin can update tenant region configuration.
    
    Verifies that users with admin API keys can successfully update a tenant's
    home region and cross-region failover policy, ensuring routing respects
    tenant assigned region and data-residency policy.
    """
    logger.info("Testing admin can update tenant region configuration")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.put(
            "/v1/admin/tenants/tenant_123/region",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            json={
                "home_region": "us-west-2",
                "allow_cross_region_failover": True,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": "tenant_123",
        "home_region": "us-west-2",
        "allow_cross_region_failover": True,
    }
    
    logger.info("Admin tenant region update test passed")


@pytest.mark.asyncio
async def test_rejects_unknown_tenant_region(app):
    """
    Test that unknown regions are rejected.
    
    Verifies that the API rejects requests with unsupported region names,
    returning a 422 Unprocessable Entity status with an unsupported_region error.
    This prevents routing traffic to non-existent or unavailable regions.
    """
    logger.info("Testing unknown region rejection")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.put(
            "/v1/admin/tenants/tenant_123/region",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            json={
                "home_region": "ap-south-1",
                "allow_cross_region_failover": False,
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "unsupported_region"
    
    logger.info("Unknown region rejection test passed")


@pytest.mark.asyncio
async def test_non_admin_cannot_update_tenant_region(app):
    """
    Test that non-admin keys cannot update tenant region.
    
    Verifies that API keys without admin privileges are forbidden from modifying
    tenant region configurations, returning a 403 Forbidden status.
    """
    logger.info("Testing non-admin key cannot update tenant region")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.put(
            "/v1/admin/tenants/tenant_123/region",
            headers={
                "Authorization": "Bearer stream-only-test-key",
            },
            json={
                "home_region": "eu-west-1",
                "allow_cross_region_failover": False,
            },
        )

    assert response.status_code == 403
    
    logger.info("Non-admin key rejection test passed")
