"""
Tests for Redis-backed tenant rate limiting.

This module tests the rate limiting functionality for tenant operations, including
fixed-window rate limit keys, TTL expiration, request allowance under limits, and
429 rejection when limits are exceeded. Rate limiting is critical for protecting
backend resources and ensuring fair usage across tenants.

Run tests:
    pytest tests/test_rate_limits.py

Purpose:
This verifies Redis-backed tenant rate limits for REST transcription and admin operations,
including fixed-window keys, TTLs, allowed requests, and 429 rejection when the limit is
exceeded. The guide requires Redis for ephemeral per-tenant rate limits and recommends
conservative defaults of 30 transcriptions/minute and 5 admin calls/minute.
"""
import logging

import pytest
from fastapi import HTTPException

from stt_server.rate_limits import enforce_rate_limit, rate_limit_key

logger = logging.getLogger(__name__)


class FakeRedis:
    """
    Fake Redis client for testing rate limiting.
    
    Simulates Redis operations with in-memory state for testing rate limit behavior.
    """
    def __init__(self):
        """Initialize the fake Redis client with empty state."""
        self.values = {}
        self.expirations = {}

    async def incr(self, key: str) -> int:
        """
        Increment a counter value.
        
        Args:
            key: The Redis key for the counter.
            
        Returns:
            The incremented value.
        """
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key: str, ttl_seconds: int) -> None:
        """
        Set a TTL on a key.
        
        Args:
            key: The Redis key to expire.
            ttl_seconds: Time-to-live in seconds.
        """
        self.expirations[key] = ttl_seconds


def test_rate_limit_key_includes_tenant_operation_and_window(monkeypatch):
    """
    Test that rate limit key includes tenant, operation, and time window.
    
    Verifies that the rate limit key is constructed correctly with tenant ID,
    operation type, and time window identifier for fixed-window rate limiting.
    
    Args:
        monkeypatch: Pytest fixture for modifying environment variables
    """
    logger.info("Testing rate limit key construction")
    
    monkeypatch.setattr("time.time", lambda: 120)

    key = rate_limit_key(
        tenant_id="tenant_123",
        operation="stt_transcribe",
        window_seconds=60,
    )

    assert key == "stt:tenant:tenant_123:rate:stt_transcribe:2"
    
    logger.info("Rate limit key construction test passed")


@pytest.mark.asyncio
async def test_allows_requests_under_limit(monkeypatch):
    """
    Test that requests are allowed when under the rate limit.
    
    Verifies that when the number of requests is below the configured limit,
    the rate limiter allows the requests without raising an exception.
    
    Args:
        monkeypatch: Pytest fixture for modifying environment variables
    """
    logger.info("Testing requests allowed under rate limit")
    
    from stt_server import rate_limits

    fake_redis = FakeRedis()

    monkeypatch.setattr(
        rate_limits,
        "redis_client",
        fake_redis,
    )

    await enforce_rate_limit(
        tenant_id="tenant_123",
        operation="stt_transcribe",
        limit=2,
        window_seconds=60,
    )

    await enforce_rate_limit(
        tenant_id="tenant_123",
        operation="stt_transcribe",
        limit=2,
        window_seconds=60,
    )
    
    logger.info("Requests under limit test passed")


@pytest.mark.asyncio
async def test_rejects_requests_over_limit(monkeypatch):
    """
    Test that requests are rejected when over the rate limit.
    
    Verifies that when the number of requests exceeds the configured limit,
    the rate limiter raises an HTTPException with status 429 and appropriate
    error details.
    
    Args:
        monkeypatch: Pytest fixture for modifying environment variables
    """
    logger.info("Testing requests rejected over rate limit")
    
    from stt_server import rate_limits

    fake_redis = FakeRedis()

    monkeypatch.setattr(
        rate_limits,
        "redis_client",
        fake_redis,
    )

    await enforce_rate_limit(
        tenant_id="tenant_123",
        operation="admin",
        limit=1,
        window_seconds=60,
    )

    with pytest.raises(HTTPException) as exc:
        await enforce_rate_limit(
            tenant_id="tenant_123",
            operation="admin",
            limit=1,
            window_seconds=60,
        )

    assert exc.value.status_code == 429
    assert exc.value.detail["error"] == "rate_limit_exceeded"
    assert exc.value.detail["operation"] == "admin"
    
    logger.info("Requests over limit rejection test passed")


@pytest.mark.asyncio
async def test_sets_expiration_on_first_counter_write(monkeypatch):
    """
    Test that expiration is set on the first counter write.
    
    Verifies that when a rate limit counter is first created, the TTL is
    set to the configured window duration to ensure fixed-window behavior.
    
    Args:
        monkeypatch: Pytest fixture for modifying environment variables
    """
    logger.info("Testing expiration set on first counter write")
    
    from stt_server import rate_limits

    fake_redis = FakeRedis()

    monkeypatch.setattr(
        rate_limits,
        "redis_client",
        fake_redis,
    )

    await enforce_rate_limit(
        tenant_id="tenant_123",
        operation="stt_transcribe",
        limit=30,
        window_seconds=60,
    )

    assert list(fake_redis.expirations.values()) == [60]
    
    logger.info("Expiration on first write test passed")

# Run:
#
# pytest tests/test_rate_limits.py
#
# This verifies Redis-backed tenant rate limits for REST transcription and admin operations, including fixed-window keys, TTLs, allowed requests, and 429 rejection when the limit is exceeded. The guide requires Redis for ephemeral per-tenant rate limits and recommends conservative defaults of 30 transcriptions/minute and 5 admin calls/minute.
