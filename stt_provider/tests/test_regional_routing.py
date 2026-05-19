"""
Tests for tenant home-region enforcement.

This module tests the regional routing decision logic for co-located GPU regions.
Tests verify that requests are allowed in the tenant's home region, blocked when
cross-region failover is disabled, and allowed when failover is enabled.

Run tests:
    pytest tests/test_regional_routing.py

Purpose:
This verifies tenant home-region enforcement for co-located GPU regions, including
normal in-region routing, blocked cross-region routing, and explicit failover allowance.
The guide's co-located GPU regions step requires routing to respect tenant data-residency
policy and regional GPU placement.
"""
import logging

from stt_server.regional_routing import decide_regional_route

logger = logging.getLogger(__name__)


def test_allows_request_in_tenant_home_region():
    """
    Test that requests are allowed in the tenant's home region.
    
    Verifies that when a request originates from the tenant's configured home region,
    the routing decision allows the request with no blocking reason.
    """
    logger.info("Testing request allowed in tenant home region")
    
    decision = decide_regional_route(
        tenant_id="tenant_123",
        home_region="us-east-1",
        request_region="us-east-1",
    )

    assert decision.allowed is True
    assert decision.reason is None
    
    logger.info("Home region request allowed test passed")


def test_blocks_cross_region_request_when_failover_is_disabled():
    """
    Test that cross-region requests are blocked when failover is disabled.
    
    Verifies that when a request originates from a different region and cross-region
    failover is disabled, the routing decision blocks the request with a home region
    mismatch reason.
    """
    logger.info("Testing cross-region request blocked when failover disabled")
    
    decision = decide_regional_route(
        tenant_id="tenant_123",
        home_region="us-east-1",
        request_region="eu-west-1",
        allow_cross_region_failover=False,
    )

    assert decision.allowed is False
    assert decision.reason == "tenant_home_region_mismatch"
    
    logger.info("Cross-region request blocked test passed")


def test_allows_cross_region_request_when_failover_is_enabled():
    """
    Test that cross-region requests are allowed when failover is enabled.
    
    Verifies that when a request originates from a different region but cross-region
    failover is enabled, the routing decision allows the request with a failover
    allowed reason.
    """
    logger.info("Testing cross-region request allowed when failover enabled")
    
    decision = decide_regional_route(
        tenant_id="tenant_123",
        home_region="us-east-1",
        request_region="us-west-2",
        allow_cross_region_failover=True,
    )

    assert decision.allowed is True
    assert decision.reason == "cross_region_failover_allowed"
    
    logger.info("Cross-region request allowed test passed")

# Run:
#
# pytest tests/test_regional_routing.py
#
# This verifies tenant home-region enforcement for co-located GPU regions, including normal in-region routing, blocked cross-region routing, and explicit failover allowance. The guide's co-located GPU regions step requires routing to respect tenant data-residency policy and regional GPU placement.
