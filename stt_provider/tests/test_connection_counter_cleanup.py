"""
Tests for connection counter cleanup safety.

This module tests the safety mechanisms for Redis active-connection counters.
Tests verify that counters cannot drift below zero, ensuring tenant limits and
autoscaling inputs remain safe after disconnect retries or duplicate cleanup operations.

Run tests:
    pytest tests/test_connection_counter_cleanup.py

Purpose:
This ensures that the connection counter cleanup logic properly clamps negative values to zero
and sets appropriate TTLs, preventing counter drift that could affect tenant limit enforcement
and autoscaling decisions.
"""
import logging

import pytest

from stt_server.connection_counter_cleanup import safe_decrement_counter

logger = logging.getLogger(__name__)


class FakeRedis:
    """
    Fake Redis client for testing.
    
    Simulates Redis operations with in-memory state for testing counter behavior.
    """
    def __init__(self, value: int):
        """
        Initialize the fake Redis client.
        
        Args:
            value: Initial counter value.
        """
        self.value = value
        self.expired_key = None
        self.expired_ttl = None

    async def decr(self, key: str) -> int:
        """
        Decrement a counter value.
        
        Args:
            key: The Redis key for the counter.
            
        Returns:
            The decremented value.
        """
        self.value -= 1
        return self.value

    async def set(self, key: str, value: int) -> None:
        """
        Set a counter value.
        
        Args:
            key: The Redis key for the counter.
            value: The value to set.
        """
        self.value = value

    async def expire(self, key: str, ttl_seconds: int) -> None:
        """
        Set a TTL on a key.
        
        Args:
            key: The Redis key to expire.
            ttl_seconds: Time-to-live in seconds.
        """
        self.expired_key = key
        self.expired_ttl = ttl_seconds


@pytest.mark.asyncio
async def test_safe_decrement_keeps_positive_counter(monkeypatch):
    """
    Test that safe decrement keeps positive counters valid.
    
    Verifies that when decrementing a counter with a positive value, the counter
    is decremented normally and the TTL is set appropriately.
    """
    logger.info("Testing safe decrement keeps positive counter valid")
    
    from stt_server import connection_counter_cleanup

    fake_redis = FakeRedis(value=3)

    monkeypatch.setattr(
        connection_counter_cleanup,
        "redis_client",
        fake_redis,
    )

    await safe_decrement_counter(
        "stt:tenant:tenant_123:active_connections",
        ttl_seconds=7200,
    )

    assert fake_redis.value == 2
    assert fake_redis.expired_ttl == 7200
    
    logger.info("Positive counter decrement test passed")


@pytest.mark.asyncio
async def test_safe_decrement_clamps_negative_counter_to_zero(monkeypatch):
    """
    Test that safe decrement clamps negative counters to zero.
    
    Verifies that when decrementing a counter that would go negative, the counter
    is clamped to zero to prevent drift, and the TTL is set appropriately.
    """
    logger.info("Testing safe decrement clamps negative counter to zero")
    
    from stt_server import connection_counter_cleanup

    fake_redis = FakeRedis(value=0)

    monkeypatch.setattr(
        connection_counter_cleanup,
        "redis_client",
        fake_redis,
    )

    await safe_decrement_counter(
        "stt:tenant:tenant_123:active_connections",
        ttl_seconds=7200,
    )

    assert fake_redis.value == 0
    assert fake_redis.expired_ttl == 7200
    
    logger.info("Negative counter clamping test passed")
