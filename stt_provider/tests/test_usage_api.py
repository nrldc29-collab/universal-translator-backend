"""
Tests for usage API endpoint.

This module tests the usage API endpoint for retrieving tenant usage statistics.
Tests verify that API keys with usage-read scope can view usage, stream-only keys
are blocked, and invalid query parameters are rejected.

Run tests:
    pytest tests/test_usage_api.py

Purpose:
This ensures that the externalized usage API properly enforces access control:
scoped keys with usage-read permission can read tenant usage, stream-only keys
are blocked from viewing usage, and invalid query windows are rejected with
validation errors.
"""
import logging

import pytest
from httpx import AsyncClient

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_usage_read_scope_can_view_usage(app):
    """
    Test that usage-read scope can view usage statistics.
    
    Verifies that API keys with usage-read scope can successfully retrieve
    tenant usage statistics with the correct tenant ID and time window.
    """
    logger.info("Testing usage-read scope can view usage")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/v1/usage",
            headers={
                "Authorization": "Bearer usage-read-test-key",
            },
            params={
                "tenant_id": "tenant_123",
                "days": 30,
            },
        )

    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant_123"
    assert response.json()["days"] == 30
    assert "usage" in response.json()
    
    logger.info("Usage-read scope test passed")


@pytest.mark.asyncio
async def test_stream_only_scope_cannot_view_usage(app):
    """
    Test that stream-only scope cannot view usage statistics.
    
    Verifies that API keys with stream-only scope are denied access to the
    usage API with a 403 Forbidden status.
    """
    logger.info("Testing stream-only scope cannot view usage")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/v1/usage",
            headers={
                "Authorization": "Bearer stream-only-test-key",
            },
            params={
                "tenant_id": "tenant_123",
                "days": 30,
            },
        )

    assert response.status_code == 403
    
    logger.info("Stream-only scope rejection test passed")


@pytest.mark.asyncio
async def test_usage_days_must_be_valid(app):
    """
    Test that usage days parameter must be valid.
    
    Verifies that invalid query parameters (e.g., days=0) are rejected with
    a 422 Unprocessable Entity validation error.
    """
    logger.info("Testing usage days parameter validation")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/v1/usage",
            headers={
                "Authorization": "Bearer usage-read-test-key",
            },
            params={
                "tenant_id": "tenant_123",
                "days": 0,
            },
        )

    assert response.status_code == 422
    
    logger.info("Usage days validation test passed")
