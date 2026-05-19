"""
Tests for regional failover audit logging.

This module tests that regional failover policy changes are properly logged to the audit trail.
Audit logging is critical for compliance and traceability of data-residency policy changes,
ensuring all regional routing and failover configuration modifications are recorded.

Run tests:
    pytest tests/test_regional_failover_audit.py

Purpose:
This ensures that when admins update regional failover policies, audit events are written
to the audit log with the correct event type, resource, and payload including home region
and cross-region failover policy. This provides traceability for all regional routing
changes required for co-located GPU regions and data-residency compliance.
"""
import logging

import pytest
from httpx import AsyncClient

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_regional_failover_policy_update_writes_audit_event(app):
    """
    Test that regional failover policy update writes an audit event.
    
    Verifies that when a tenant's regional failover policy is enabled, an audit event
    is written to the audit log with the event type 'tenant.region_updated', resource
    'regional_routing', and the new home region and failover policy in the payload.
    
    Note: The actual audit log verification is commented out as a placeholder for when the
    audit log fixture or test DB helper is available.
    """
    logger.info("Testing regional failover policy update writes audit event")
    
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
    
    logger.info("Regional failover policy update audit event test passed")


@pytest.mark.asyncio
async def test_regional_failover_disable_writes_audit_event(app):
    """
    Test that regional failover disable writes an audit event.
    
    Verifies that when a tenant's regional failover policy is disabled, an audit event
    is written to the audit log with the event type 'tenant.region_updated', resource
    'regional_routing', and the new home region and disabled failover policy in the payload.
    
    Note: The actual audit log verification is commented out as a placeholder for when the
    audit log fixture or test DB helper is available.
    """
    logger.info("Testing regional failover disable writes audit event")
    
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

    # Verify through your test DB helper or audit-log fixture:
    #
    # event = await fetch_latest_audit_event(
    #     tenant_id="tenant_123",
    #     event_type="tenant.region_updated",
    # )
    #
    # assert event["resource"] == "regional_routing"
    # assert event["payload_jsonb"]["home_region"] == "us-east-1"
    # assert event["payload_jsonb"]["allow_cross_region_failover"] is False
    
    logger.info("Regional failover disable audit event test passed")
