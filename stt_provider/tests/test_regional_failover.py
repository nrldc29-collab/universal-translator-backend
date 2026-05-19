"""
Tests for regional failover policy controls.

This module tests the tenant-level controls for regional failover behavior.
Tests verify that admins can enable or disable cross-region failover, tenants can be
moved to approved target regions, and unsupported regions are rejected.

Run tests:
    pytest tests/test_regional_failover.py

Purpose:
This ensures that the regional failover controls properly allow admins to configure
tenant failover policies while preventing routing to unsupported regions. This supports
the co-located GPU regions requirement that routing must consider tenant assigned region,
data-residency policy, regional GPU capacity, regional health, and failover policy.
"""
import logging

import pytest
from httpx import AsyncClient

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_admin_can_enable_cross_region_failover_policy(app):
    """
    Test that admin can enable cross-region failover policy.
    
    Verifies that users with admin API keys can successfully enable cross-region
    failover for a tenant, allowing traffic to be routed to other regions when
    the home region is unavailable or at capacity.
    """
    logger.info("Testing admin can enable cross-region failover policy")
    
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
    
    logger.info("Cross-region failover enable test passed")


@pytest.mark.asyncio
async def test_admin_can_disable_cross_region_failover_policy(app):
    """
    Test that admin can disable cross-region failover policy.
    
    Verifies that users with admin API keys can successfully disable cross-region
    failover for a tenant, ensuring traffic remains in the assigned home region
    for data-residency compliance.
    """
    logger.info("Testing admin can disable cross-region failover policy")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.put(
            "/v1/admin/tenants/tenant_123/region",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            json={
                "home_region": "us-east-1",
                "allow_cross_region_failover": False,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": "tenant_123",
        "home_region": "us-east-1",
        "allow_cross_region_failover": False,
    }
    
    logger.info("Cross-region failover disable test passed")


@pytest.mark.asyncio
async def test_unknown_failover_region_is_rejected(app):
    """
    Test that unknown failover regions are rejected.
    
    Verifies that the API rejects requests with unsupported region names,
    returning a 422 Unprocessable Entity status with an unsupported_region error.
    This prevents routing traffic to non-existent or unavailable regions.
    """
    logger.info("Testing unknown failover region is rejected")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.put(
            "/v1/admin/tenants/tenant_123/region",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            json={
                "home_region": "ap-south-1",
                "allow_cross_region_failover": True,
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "unsupported_region"
    
    logger.info("Unknown region rejection test passed")
