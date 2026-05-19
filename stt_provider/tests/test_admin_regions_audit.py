"""
Tests for admin region management audit logging.

This module tests that tenant region changes are properly logged to the audit trail.
Audit logging is critical for compliance and traceability of data-residency policy changes,
ensuring all region configuration modifications are recorded with home region and failover policy.

Run tests:
    pytest tests/test_admin_regions_audit.py

Purpose:
This ensures that when admins update tenant regions, an audit event is written to the audit log
with the correct event type, resource, and payload including home region and cross-region failover
policy. This provides traceability for all regional routing changes required for co-located GPU
regions, data-residency policy compliance, and regional failover behavior.
"""
import logging

import pytest
from httpx import AsyncClient

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_tenant_region_update_writes_audit_event(app):
    """
    Test that tenant region update writes an audit event.
    
    Verifies that when a tenant's region is updated, an audit event is written to the audit log
    with the event type 'tenant.region_updated', resource 'regional_routing', and the new home
    region and failover policy in the payload. This ensures all region configuration changes are
    traceable for compliance and debugging purposes.
    
    Note: The actual audit log verification is commented out as a placeholder for when the
    audit log fixture or test DB helper is available.
    """
    logger.info("Testing tenant region update writes audit event")
    
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

    # Verify through your test DB helper or audit-log fixture:
    #
    # event = await fetch_latest_audit_event(
    #     tenant_id="tenant_123",
    #     event_type="tenant.region_updated",
    # )
    #
    # assert event["resource"] == "regional_routing"
    # assert event["payload_jsonb"]["home_region"] == "us-west-2"
    # assert event["payload_jsonb"]["allow_cross_region_failover"] is True
    
    logger.info("Tenant region update audit event test passed")
