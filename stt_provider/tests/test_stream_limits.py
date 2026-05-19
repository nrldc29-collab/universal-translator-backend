"""
Tests for tenant stream limit enforcement.

This module tests the enforcement of per-tenant concurrent stream limits using Redis
active-connection counters. Tests verify that streams are allowed when under limit,
rejected when at limit, and that missing counters are treated as zero.

Run tests:
    pytest tests/test_stream_limits.py

Purpose:
This ensures that tenant stream limits are properly enforced using Redis counters,
supporting the guide's Phase 2B requirement to externalize active connection state
into Redis for per-tenant limits and autoscaling.
"""
import logging

import pytest
from fastapi import WebSocketException

from stt_server.stream_limits import enforce_tenant_stream_limit

logger = logging.getLogger(__name__)


class FakeRedis:
    """
    Fake Redis client for testing stream limit enforcement.
    
    Simulates Redis GET operations for stream counter values.
    """
    def __init__(self, value):
        """
        Initialize the fake Redis with a predefined value.
        
        Args:
            value: The value to return from GET operations.
        """
        self.value = value

    async def get(self, key):
        """
        Simulate Redis GET operation.
        
        Args:
            key: The Redis key to retrieve.
            
        Returns:
            The predefined value set during initialization.
        """
        return self.value


@pytest.mark.asyncio
async def test_allows_stream_when_under_limit(monkeypatch):
    """
    Test that stream is allowed when under the limit.
    
    Verifies that when the current stream count (3) is below the maximum limit (5),
    the stream limit enforcement passes without raising an exception.
    """
    logger.info("Testing stream allowed when under limit")
    
    from stt_server import stream_limits

    monkeypatch.setattr(
        stream_limits,
        "redis_client",
        FakeRedis(value="3"),
    )

    await enforce_tenant_stream_limit(
        tenant_id="tenant_123",
        max_concurrent_streams=5,
    )
    
    logger.info("Stream allowed when under limit test passed")


@pytest.mark.asyncio
async def test_rejects_stream_when_at_limit(monkeypatch):
    """
    Test that stream is rejected when at the limit.
    
    Verifies that when the current stream count (5) equals the maximum limit (5),
    the stream limit enforcement raises a WebSocketException with code 1013
    and an appropriate error message.
    """
    logger.info("Testing stream rejected when at limit")
    
    from stt_server import stream_limits

    monkeypatch.setattr(
        stream_limits,
        "redis_client",
        FakeRedis(value="5"),
    )

    with pytest.raises(WebSocketException) as exc:
        await enforce_tenant_stream_limit(
            tenant_id="tenant_123",
            max_concurrent_streams=5,
        )

    assert exc.value.code == 1013
    assert exc.value.reason == "Tenant concurrent stream limit reached."
    
    logger.info("Stream rejected when at limit test passed")


@pytest.mark.asyncio
async def test_missing_counter_counts_as_zero(monkeypatch):
    """
    Test that missing counter is treated as zero.
    
    Verifies that when the Redis counter is missing (None), it is treated as zero
    and the stream limit enforcement passes without raising an exception.
    """
    logger.info("Testing missing counter counts as zero")
    
    from stt_server import stream_limits

    monkeypatch.setattr(
        stream_limits,
        "redis_client",
        FakeRedis(value=None),
    )

    await enforce_tenant_stream_limit(
        tenant_id="tenant_123",
        max_concurrent_streams=1,
    )
    
    logger.info("Missing counter counts as zero test passed")
