"""
Connection counter cleanup module for Redis state management.

This module provides utility functions for safely managing Redis connection counters,
preventing negative values that can occur from duplicate disconnect handling, pod
restarts, or cleanup retries. Ensures Redis state remains reliable for tenant limits
and autoscaling.
"""
import logging

import redis.asyncio as redis

from stt_server.connection_counters import redis_client

logger = logging.getLogger(__name__)


async def clamp_counter_to_zero(key: str) -> None:
    """
    Clamp a Redis counter value to zero if it is negative.
    
    Checks the current value of a Redis counter and resets it to zero if
    it has drifted below zero. Used to clean up stale or corrupted
    counter values.
    
    Args:
        key: Redis key for the counter to clamp
    """
    try:
        value = await redis_client.get(key)

        if value is None:
            logger.debug(f"Counter key '{key}' does not exist, skipping clamp")
            return

        if int(value) < 0:
            await redis_client.set(key, 0)
            logger.warning(f"Clamped negative counter '{key}' from {value} to 0")
    except redis.RedisError as e:
        logger.error(f"Failed to clamp counter '{key}': {e}")
        raise


async def safe_decrement_counter(key: str, ttl_seconds: int = 7200) -> None:
    """
    Safely decrement a Redis counter with floor at zero.
    
    Decrements the Redis counter value and ensures it never goes below zero
    by clamping to zero if necessary. Also sets expiration on the key for
    automatic cleanup.
    
    Args:
        key: Redis key for the counter to decrement
        ttl_seconds: Time-to-live for the counter key in seconds (default: 7200)
    """
    try:
        value = await redis_client.decr(key)

        if value < 0:
            await redis_client.set(key, 0)
            logger.warning(f"Clamped negative counter '{key}' to 0 during decrement")
        else:
            logger.debug(f"Decremented counter '{key}' to {value}")

        await redis_client.expire(key, ttl_seconds)
    except redis.RedisError as e:
        logger.error(f"Failed to safely decrement counter '{key}': {e}")
        raise
