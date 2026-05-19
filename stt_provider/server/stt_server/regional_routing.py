"""
Regional routing decision logic for multi-region deployment.

This module provides functionality for determining whether a request should be
routed to a specific region based on tenant home region configuration and
cross-region failover settings.

Run tests:
    pytest server/tests/test_regional_routing.py

Purpose:
This ensures that requests are routed to appropriate regions based on tenant
configuration, supporting data residency requirements and latency optimization
while providing controlled cross-region failover capabilities.
"""
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RegionalRoutingDecision:
    """
    Regional routing decision result.
    
    Represents the decision made for routing a request to a specific region,
    including whether the routing is allowed and the reason for the decision.
    
    Attributes:
        tenant_id: ID of the tenant making the request
        home_region: Tenant's configured home region
        request_region: Region where the request originated
        allowed: Whether the request is allowed to be routed to this region
        reason: Optional reason explaining the routing decision
    """
    tenant_id: str
    home_region: str
    request_region: str
    allowed: bool
    reason: Optional[str] = None


def decide_regional_route(
    *,
    tenant_id: str,
    home_region: str,
    request_region: str,
    allow_cross_region_failover: bool = False,
) -> RegionalRoutingDecision:
    """
    Decide whether to route a request to a specific region.
    
    Determines if a request should be routed to the request region based on
    the tenant's home region and cross-region failover configuration.
    
    Args:
        tenant_id: ID of the tenant making the request
        home_region: Tenant's configured home region
        request_region: Region where the request originated
        allow_cross_region_failover: Whether to allow cross-region failover
        
    Returns:
        RegionalRoutingDecision with the routing decision and reason
    """
    logger.debug(
        f"Deciding regional route for tenant {tenant_id}: "
        f"home={home_region}, request={request_region}, failover={allow_cross_region_failover}"
    )
    
    # Allow if request is from tenant's home region
    if request_region == home_region:
        logger.debug(f"Request allowed: request region matches tenant home region {home_region}")
        return RegionalRoutingDecision(
            tenant_id=tenant_id,
            home_region=home_region,
            request_region=request_region,
            allowed=True,
        )

    # Allow cross-region failover if enabled
    if allow_cross_region_failover:
        logger.debug(f"Request allowed via cross-region failover to {request_region}")
        return RegionalRoutingDecision(
            tenant_id=tenant_id,
            home_region=home_region,
            request_region=request_region,
            allowed=True,
            reason="cross_region_failover_allowed",
        )

    # Deny if request region doesn't match home region and failover is disabled
    logger.debug(f"Request denied: region mismatch and cross-region failover disabled")
    return RegionalRoutingDecision(
        tenant_id=tenant_id,
        home_region=home_region,
        request_region=request_region,
        allowed=False,
        reason="tenant_home_region_mismatch",
    )
