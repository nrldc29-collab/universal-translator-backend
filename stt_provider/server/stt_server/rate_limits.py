"""
Redis-backed rate limiting module.

This module provides functionality for enforcing rate limits on API operations
using Redis for distributed state management. It supports per-tenant rate limiting
with configurable limits and time windows for transcription and admin operations.
"""
import logging
import os
import time

import redis.asyncio as redis
from fastapi import HTTPException, status

from stt_server.connection_counters import redis_client

logger = logging.getLogger(__name__)

REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "stt:")

DEFAULT_TRANSCRIPTION_LIMIT = int(
    os.getenv("TRANSCRIPTION_RATE_LIMIT_PER_MINUTE", "30")
)

DEFAULT_ADMIN_LIMIT = int(
    os.getenv("ADMIN_RATE_LIMIT_PER_MINUTE", "5")
)


def rate_limit_key(
    *,
    tenant_id: str,
    operation: str,
    window_seconds: int,
) -> str:
    """
    Generate a Redis key for rate limiting.
    
    Creates a time-windowed key for rate limiting that changes
    based on the current time window to implement sliding window
    rate limiting.
    
    Args:
        tenant_id: Tenant identifier
        operation: Operation being rate limited (e.g., "stt_transcribe", "admin")
        window_seconds: Window size in seconds
        
    Returns:
        Redis key string for the rate limit counter
    """
    current_window = int(time.time() // window_seconds)

    return (
        f"{REDIS_KEY_PREFIX}"
        f"tenant:{tenant_id}:rate:{operation}:{current_window}"
    )


async def enforce_rate_limit(
    *,
    tenant_id: str,
    operation: str,
    limit: int,
    window_seconds: int = 60,
) -> None:
    """
    Enforce a rate limit for a tenant operation.
    
    Increments the rate limit counter and raises an HTTP 429 exception
    if the limit has been exceeded. Sets expiration on the key for
    automatic cleanup after the time window.
    
    Args:
        tenant_id: Tenant identifier
        operation: Operation being rate limited
        limit: Maximum number of requests allowed in the time window
        window_seconds: Time window size in seconds (default: 60)
        
    Raises:
        HTTPException: 429 Too Many Requests if rate limit is exceeded
        redis.RedisError: If Redis operation fails
    """
    key = rate_limit_key(
        tenant_id=tenant_id,
        operation=operation,
        window_seconds=window_seconds,
    )

    try:
        current_count = await redis_client.incr(key)

        if current_count == 1:
            await redis_client.expire(key, window_seconds)

        if current_count > limit:
            logger.warning(
                f"Rate limit exceeded for tenant={tenant_id}, operation={operation}, "
                f"count={current_count}, limit={limit}"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "operation": operation,
                    "limit": limit,
                    "window_seconds": window_seconds,
                },
            )
        
        logger.debug(
            f"Rate limit check passed for tenant={tenant_id}, operation={operation}, "
            f"count={current_count}, limit={limit}"
        )
    except redis.RedisError as e:
        logger.error(f"Redis error during rate limit check: {e}")
        raise


async def enforce_transcription_rate_limit(tenant_id: str) -> None:
    """
    Enforce transcription rate limit for a tenant.
    
    Checks the transcription rate limit (default: 30 requests per minute)
    for the specified tenant.
    
    Args:
        tenant_id: Tenant identifier
    """
    await enforce_rate_limit(
        tenant_id=tenant_id,
        operation="stt_transcribe",
        limit=DEFAULT_TRANSCRIPTION_LIMIT,
    )


async def enforce_admin_rate_limit(tenant_id: str) -> None:
    """
    Enforce admin operation rate limit for a tenant.
    
    Checks the admin operation rate limit (default: 5 requests per minute)
    for the specified tenant.
    
    Args:
        tenant_id: Tenant identifier
    """
    await enforce_rate_limit(
        tenant_id=tenant_id,
        operation="admin",
        limit=DEFAULT_ADMIN_LIMIT,
    )

# Call it at the start of REST transcription routes:
#
# from stt_server.rate_limits import enforce_transcription_rate_limit
#
# await enforce_transcription_rate_limit(
#     tenant_id=str(tenant.id),
# )
#
# Call it at the start of admin routes:
#
# from stt_server.rate_limits import enforce_admin_rate_limit
#
# await enforce_admin_rate_limit(
#     tenant_id=str(tenant.id),
# )
#
# This adds Redis-backed per-tenant rate-limit counters for transcription and admin operations, matching the guide's requirement to keep ephemeral rate-limit state in Redis while using conservative defaults of 30 transcriptions/minute and 5 admin calls/minute
