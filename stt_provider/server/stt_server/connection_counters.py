"""
Redis-backed connection counter module.

This module provides functionality for tracking active WebSocket connections
using Redis for distributed state management. It supports tenant-level and
pod-level connection counting with automatic expiration for safe cleanup.
"""
import logging
import os

import redis.asyncio as redis

from stt_server.connection_counter_cleanup import safe_decrement_counter

logger = logging.getLogger(__name__)

REDIS_KEY_PREFIX = os.getenv("REDIS_KEY_PREFIX", "stt:")
REDIS_URL = os.environ["REDIS_URL"]

# Global Redis client for connection counting
redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
)


def tenant_active_connections_key(tenant_id: str) -> str:
    """
    Generate the Redis key for tenant active connections.
    
    Args:
        tenant_id: Tenant identifier
        
    Returns:
        Redis key string for tenant active connections
    """
    return f"{REDIS_KEY_PREFIX}tenant:{tenant_id}:active_connections"


def pod_active_connections_key(pod_name: str) -> str:
    """
    Generate the Redis key for pod active connections.
    
    Args:
        pod_name: Pod name identifier
        
    Returns:
        Redis key string for pod active connections
    """
    return f"{REDIS_KEY_PREFIX}pod:{pod_name}:active_connections"


async def increment_active_connections(
    *,
    tenant_id: str,
    pod_name: str,
    ttl_seconds: int = 7200,
) -> None:
    """
    Increment active connection counters for tenant and pod.
    
    Atomically increments both tenant-level and pod-level connection
    counters in Redis using a transaction. Sets expiration on both
    keys to ensure stale counts are cleaned up automatically.
    
    Args:
        tenant_id: Tenant identifier
        pod_name: Pod name identifier
        ttl_seconds: Time-to-live for counter keys in seconds (default: 7200)
    """
    tenant_key = tenant_active_connections_key(tenant_id)
    pod_key = pod_active_connections_key(pod_name)

    try:
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.incr(tenant_key)
            pipe.expire(tenant_key, ttl_seconds)
            pipe.incr(pod_key)
            pipe.expire(pod_key, ttl_seconds)
            await pipe.execute()
        logger.debug(f"Incremented connection counters for tenant={tenant_id}, pod={pod_name}")
    except redis.RedisError as e:
        logger.error(f"Failed to increment connection counters: {e}")
        raise


async def decrement_active_connections(
    *,
    tenant_id: str,
    pod_name: str,
    ttl_seconds: int = 7200,
) -> None:
    """
    Decrement active connection counters for tenant and pod.
    
    Safely decrements both tenant-level and pod-level connection counters
    using a cleanup function that prevents negative values and removes
    keys when the count reaches zero.
    
    Args:
        tenant_id: Tenant identifier
        pod_name: Pod name identifier
        ttl_seconds: Time-to-live for counter keys in seconds (default: 7200)
    """
    try:
        await safe_decrement_counter(
            tenant_active_connections_key(tenant_id),
            ttl_seconds=ttl_seconds,
        )

        await safe_decrement_counter(
            pod_active_connections_key(pod_name),
            ttl_seconds=ttl_seconds,
        )
        logger.debug(f"Decremented connection counters for tenant={tenant_id}, pod={pod_name}")
    except redis.RedisError as e:
        logger.error(f"Failed to decrement connection counters: {e}")
        raise

# Call it when a WebSocket connects:
#
# import os
#
# from stt_server.connection_counters import increment_active_connections
#
# pod_name = os.getenv("POD_NAME", "unknown")
#
# await increment_active_connections(
#     tenant_id=str(tenant.id),
#     pod_name=pod_name,
# )
#
# Call it in the WebSocket cleanup path:
#
# from stt_server.connection_counters import decrement_active_connections
#
# await decrement_active_connections(
#     tenant_id=str(tenant.id),
#     pod_name=pod_name,
# )
#
# Install the Redis dependency:
#
# pip install redis
#
# This adds Redis-backed active connection counters for tenant limits, gateway autoscaling, and safe connection-draining visibility, matching the Phase 2B requirement to externalize ephemeral active-connection state into Redis.
