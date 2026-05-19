"""
Stream limit enforcement for tenant connections.
"""
import logging
import os

from fastapi import WebSocketException, status

from stt_server.connection_counters import redis_client, tenant_active_connections_key

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENT_STREAMS = int(os.getenv("MAX_CONCURRENT_STREAMS_PER_TENANT", "100"))


async def get_active_stream_count(tenant_id: str) -> int:
    if redis_client is None:
        return 0
    value = await redis_client.get(tenant_active_connections_key(tenant_id))
    count = int(value or 0)
    logger.debug("Active stream count for tenant %s: %s", tenant_id, count)
    return count


async def enforce_tenant_stream_limit(
    *,
    tenant_id: str,
    max_concurrent_streams: int | None = None,
) -> None:
    limit = max_concurrent_streams or DEFAULT_MAX_CONCURRENT_STREAMS
    active_count = await get_active_stream_count(tenant_id)
    if active_count >= limit:
        logger.warning("Tenant %s reached stream limit %s/%s", tenant_id, active_count, limit)
        raise WebSocketException(
            code=status.WS_1013_TRY_AGAIN_LATER,
            reason="Tenant concurrent stream limit reached.",
        )
