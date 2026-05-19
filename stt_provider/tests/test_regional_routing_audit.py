"""
Tests for regional routing decision audit logging.

This module tests that regional routing decisions are properly logged to the audit trail.
Audit logging is critical for compliance and traceability of regional routing behavior,
ensuring all routing decisions (allowed or blocked) are recorded with appropriate context.

Run tests:
    pytest tests/test_regional_routing_audit.py

Purpose:
This ensures that regional routing decisions are audited for both allowed in-region routing
and blocked cross-region routing. This provides traceability for all regional routing
decisions required for co-located GPU regions, data-residency compliance, and regional health monitoring.
"""
import logging

import pytest

from stt_server.regional_routing import RegionalRoutingDecision
from stt_server.regional_routing_audit import audit_regional_routing_decision

logger = logging.getLogger(__name__)


class FakeDb:
    """
    Fake database for testing audit event logging.
    
    Records executed queries and their arguments for verification.
    """
    def __init__(self):
        """Initialize the fake database with an empty event list."""
        self.events = []

    async def execute(self, query, *args):
        """
        Record a database query execution.
        
        Args:
            query: The SQL query that would be executed.
            *args: Arguments passed to the query.
        """
        self.events.append(
            {
                "query": query,
                "args": args,
            }
        )
        return None


@pytest.mark.asyncio
async def test_audit_regional_route_allowed_event():
    """
    Test that allowed regional routing writes an audit event.
    
    Verifies that when a regional routing decision allows traffic to the home region,
    an audit event is written to the audit log with the event type 'tenant.regional_route_allowed',
    resource 'regional_routing', and the relevant region and actor information.
    """
    logger.info("Testing allowed regional routing writes audit event")
    
    db = FakeDb()

    decision = RegionalRoutingDecision(
        tenant_id="tenant_123",
        home_region="us-east-1",
        request_region="us-east-1",
        allowed=True,
    )

    await audit_regional_routing_decision(
        db,
        decision=decision,
        actor_id="api_key_123",
    )

    assert len(db.events) == 1

    event_args = str(db.events[0]["args"])

    assert "tenant.regional_route_allowed" in event_args
    assert "regional_routing" in event_args
    assert "us-east-1" in event_args
    assert "api_key_123" in event_args
    
    logger.info("Allowed regional routing audit event test passed")


@pytest.mark.asyncio
async def test_audit_regional_route_blocked_event():
    """
    Test that blocked regional routing writes an audit event.
    
    Verifies that when a regional routing decision blocks cross-region traffic,
    an audit event is written to the audit log with the event type 'tenant.regional_route_blocked',
    resource 'regional_routing', and the home region, request region, and blocking reason.
    """
    logger.info("Testing blocked regional routing writes audit event")
    
    db = FakeDb()

    decision = RegionalRoutingDecision(
        tenant_id="tenant_123",
        home_region="us-east-1",
        request_region="eu-west-1",
        allowed=False,
        reason="tenant_home_region_mismatch",
    )

    await audit_regional_routing_decision(
        db,
        decision=decision,
        actor_id="api_key_123",
    )

    assert len(db.events) == 1

    event_args = str(db.events[0]["args"])

    assert "tenant.regional_route_blocked" in event_args
    assert "regional_routing" in event_args
    assert "us-east-1" in event_args
    assert "eu-west-1" in event_args
    assert "tenant_home_region_mismatch" in event_args
    
    logger.info("Blocked regional routing audit event test passed")
