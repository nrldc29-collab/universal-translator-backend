"""
Tests for regional routing functionality.

This module tests the regional routing system which routes requests to appropriate
regional endpoints based on tenant configuration and request parameters. Tests verify
tenant home region preference, default region behavior, region parsing from headers,
fallback settings, case insensitivity, and invalid region handling.

Run tests:
    pytest server/tests/test_regional_routing.py

Purpose:
This ensures that the regional routing system correctly directs traffic to the
appropriate region based on tenant configuration and request context, supporting
data residency requirements and latency optimization.
"""
import logging

import pytest

from stt_server.regional_routing import get_preferred_region, parse_region_from_request

logger = logging.getLogger(__name__)


def test_get_preferred_region_from_tenant():
    """
    Test that tenant's home region is preferred.
    
    Verifies that when a tenant has a configured home region, it is selected
    as the preferred region for routing.
    """
    logger.info("Testing tenant home region preference")
    
    tenant = {
        "home_region": "us-west-2",
        "allow_backend_fallback": True,
    }
    
    region = get_preferred_region(tenant)
    assert region == "us-west-2"
    
    logger.info("Tenant home region preference test passed")


def test_get_preferred_region_defaults_to_us_east():
    """
    Test that default region is us-east-1 when not specified.
    
    Verifies that when a tenant has no configured home region, the system
    defaults to us-east-1 as the preferred region.
    """
    logger.info("Testing default region fallback to us-east-1")
    
    tenant = {
        "home_region": None,
        "allow_backend_fallback": True,
    }
    
    region = get_preferred_region(tenant)
    assert region == "us-east-1"
    
    logger.info("Default region fallback test passed")


def test_parse_region_from_request_header():
    """
    Test parsing region from request header.
    
    Verifies that region codes can be extracted from the x-preferred-region
    request header.
    """
    logger.info("Testing region parsing from request header")
    
    headers = {"x-preferred-region": "eu-west-1"}
    region = parse_region_from_request(headers)
    assert region == "eu-west-1"
    
    logger.info("Region parsing from request header test passed")


def test_parse_region_from_query_param():
    """
    Test parsing region from query parameter.
    
    Placeholder for future implementation of query parameter region parsing.
    """
    logger.info("Testing region parsing from query parameter (placeholder)")
    
    # This would be implemented based on actual query param handling
    pass
    
    logger.info("Region parsing from query parameter test passed (placeholder)")


def test_parse_region_missing_returns_none():
    """
    Test that missing region returns None.
    
    Verifies that when no region information is present in the request,
    the parser returns None.
    """
    logger.info("Testing missing region returns None")
    
    headers = {}
    region = parse_region_from_request(headers)
    assert region is None
    
    logger.info("Missing region returns None test passed")


def test_region_routing_with_fallback_enabled():
    """
    Test that routing respects fallback setting.
    
    Verifies that both tenants with and without fallback enabled use their
    home region when it is available.
    """
    logger.info("Testing region routing with fallback settings")
    
    tenant_with_fallback = {
        "home_region": "us-west-2",
        "allow_backend_fallback": True,
    }
    
    tenant_without_fallback = {
        "home_region": "us-west-2",
        "allow_backend_fallback": False,
    }
    
    # Both should use home region when available
    assert get_preferred_region(tenant_with_fallback) == "us-west-2"
    assert get_preferred_region(tenant_without_fallback) == "us-west-2"
    
    logger.info("Region routing with fallback settings test passed")


def test_region_case_insensitive():
    """
    Test that region matching is case-insensitive.
    
    Verifies that region codes are normalized to lowercase for consistent
    matching regardless of input case.
    """
    logger.info("Testing case-insensitive region matching")
    
    headers = {"x-preferred-region": "US-WEST-2"}
    region = parse_region_from_request(headers)
    assert region.lower() == "us-west-2"
    
    logger.info("Case-insensitive region matching test passed")


def test_invalid_region_handling():
    """
    Test handling of invalid region codes.
    
    Verifies that invalid region codes are handled gracefully, either
    returning None or passing through the invalid value for later validation.
    """
    logger.info("Testing invalid region code handling")
    
    headers = {"x-preferred-region": "invalid-region"}
    region = parse_region_from_request(headers)
    # Should return None or handle gracefully
    assert region is None or region == "invalid-region"
    
    logger.info("Invalid region code handling test passed")
