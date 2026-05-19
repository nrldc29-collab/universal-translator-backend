"""
Tests for tenant throttling functionality.

This module tests the TenantThrottler implementation which provides per-tenant
rate limiting and concurrency control for the STT service. Tests verify rate
limits (per-second and per-minute), concurrent request limits, stream limits,
request/stream release, state tracking, and tenant isolation.

Run tests:
    pytest server/tests/test_tenant_throttling.py

Purpose:
This ensures that the throttling layer properly enforces per-tenant limits
to prevent resource exhaustion and ensure fair resource allocation across
all tenants in a multi-tenant environment.
"""
import asyncio
import logging
import time

import pytest
from uuid import uuid4

from stt_server.tenant_throttling import (
    TenantThrottler,
    TenantRequestState,
    TenantStreamState,
    get_throttler,
)

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_tenant_throttler_initial_state():
    """
    Test that throttler starts with empty state.
    
    Verifies that a newly created throttler initializes with zero counts
    for requests, concurrent requests, and streams.
    """
    logger.info("Testing tenant throttler initial state")
    
    throttler = TenantThrottler()
    tenant_id = uuid4()
    
    stats = throttler.get_tenant_stats(tenant_id)
    
    assert stats["request_count"] == 0
    assert stats["concurrent_requests"] == 0
    assert stats["active_streams"] == 0
    assert stats["total_streams"] == 0
    assert stats["peak_concurrent_streams"] == 0
    
    logger.info("Initial state test passed")


@pytest.mark.asyncio
async def test_rate_limit_allows_within_limit():
    """
    Test that requests within rate limit are allowed.
    
    Verifies that a request within the configured rate limits is allowed
    without error.
    """
    logger.info("Testing rate limit allows within limit")
    
    throttler = TenantThrottler(
        max_requests_per_second=10,
        max_requests_per_minute=100,
        max_concurrent_requests=5,
    )
    tenant_id = uuid4()
    
    allowed, error = await throttler.check_rate_limit(tenant_id)
    
    assert allowed is True
    assert error is None
    
    logger.info("Rate limit allows within limit test passed")


@pytest.mark.asyncio
async def test_rate_limit_blocks_per_second():
    """
    Test that per-second rate limit is enforced.
    
    Verifies that when the per-second limit is exceeded, subsequent requests
    are blocked with an appropriate error message.
    """
    logger.info("Testing per-second rate limit enforcement")
    
    throttler = TenantThrottler(max_requests_per_second=1)
    tenant_id = uuid4()
    
    # First request should be allowed
    allowed, _ = await throttler.check_rate_limit(tenant_id)
    assert allowed is True
    
    # Immediate second request should be blocked
    allowed, error = await throttler.check_rate_limit(tenant_id)
    assert allowed is False
    assert "per second" in error.lower()
    
    logger.info("Per-second rate limit enforcement test passed")


@pytest.mark.asyncio
async def test_rate_limit_blocks_per_minute():
    """
    Test that per-minute rate limit is enforced.
    
    Verifies that when the per-minute limit is exceeded, subsequent requests
    are blocked with an appropriate error message.
    """
    logger.info("Testing per-minute rate limit enforcement")
    
    throttler = TenantThrottler(max_requests_per_minute=2)
    tenant_id = uuid4()
    
    # Allow first request
    allowed, _ = await throttler.check_rate_limit(tenant_id)
    assert allowed is True
    
    # Wait to bypass per-second limit
    await asyncio.sleep(0.1)
    
    # Allow second request
    allowed, _ = await throttler.check_rate_limit(tenant_id)
    assert allowed is True
    
    # Wait to bypass per-second limit
    await asyncio.sleep(0.1)
    
    # Third request should be blocked (per-minute limit)
    allowed, error = await throttler.check_rate_limit(tenant_id)
    assert allowed is False
    assert "per minute" in error.lower()
    
    logger.info("Per-minute rate limit enforcement test passed")


@pytest.mark.asyncio
async def test_rate_limit_blocks_concurrent():
    """
    Test that concurrent request limit is enforced.
    
    Verifies that when the concurrent request limit is exceeded, subsequent
    requests are blocked with an appropriate error message.
    """
    logger.info("Testing concurrent request limit enforcement")
    
    throttler = TenantThrottler(max_concurrent_requests=2)
    tenant_id = uuid4()
    
    # Allow first request
    allowed, _ = await throttler.check_rate_limit(tenant_id)
    assert allowed is True
    
    # Allow second request
    allowed, _ = await throttler.check_rate_limit(tenant_id)
    assert allowed is True
    
    # Third request should be blocked (concurrent limit)
    allowed, error = await throttler.check_rate_limit(tenant_id)
    assert allowed is False
    assert "concurrent" in error.lower()
    
    logger.info("Concurrent request limit enforcement test passed")


@pytest.mark.asyncio
async def test_release_request():
    """
    Test releasing requests from concurrent count.
    
    Verifies that releasing a request decrements the concurrent request count.
    """
    logger.info("Testing request release")
    
    throttler = TenantThrottler(max_concurrent_requests=1)
    tenant_id = uuid4()
    
    # Acquire request
    allowed, _ = await throttler.check_rate_limit(tenant_id)
    assert allowed is True
    
    stats = throttler.get_tenant_stats(tenant_id)
    assert stats["concurrent_requests"] == 1
    
    # Release request
    await throttler.release_request(tenant_id)
    
    stats = throttler.get_tenant_stats(tenant_id)
    assert stats["concurrent_requests"] == 0
    
    logger.info("Request release test passed")


@pytest.mark.asyncio
async def test_stream_limit_allows_within_limit():
    """
    Test that streams within limit are allowed.
    
    Verifies that a stream within the configured limit is allowed without error.
    """
    logger.info("Testing stream limit allows within limit")
    
    throttler = TenantThrottler(max_concurrent_streams_per_tenant=5)
    tenant_id = uuid4()
    
    allowed, error = await throttler.check_stream_limit(tenant_id)
    
    assert allowed is True
    assert error is None
    
    logger.info("Stream limit allows within limit test passed")


@pytest.mark.asyncio
async def test_stream_limit_blocks_when_exceeded():
    """
    Test that stream limit is enforced.
    
    Verifies that when the concurrent stream limit is exceeded, subsequent
    stream requests are blocked with an appropriate error message.
    """
    logger.info("Testing stream limit enforcement")
    
    throttler = TenantThrottler(max_concurrent_streams_per_tenant=2)
    tenant_id = uuid4()
    
    # Acquire first stream
    allowed, _ = await throttler.check_stream_limit(tenant_id)
    assert allowed is True
    
    # Acquire second stream
    allowed, _ = await throttler.check_stream_limit(tenant_id)
    assert allowed is True
    
    # Third stream should be blocked
    allowed, error = await throttler.check_stream_limit(tenant_id)
    assert allowed is False
    assert "stream" in error.lower()
    
    logger.info("Stream limit enforcement test passed")


@pytest.mark.asyncio
async def test_release_stream():
    """
    Test releasing streams from concurrent count.
    
    Verifies that releasing a stream decrements the active stream count
    while preserving the total streams count.
    """
    logger.info("Testing stream release")
    
    throttler = TenantThrottler(max_concurrent_streams_per_tenant=2)
    tenant_id = uuid4()
    
    # Acquire stream
    allowed, _ = await throttler.check_stream_limit(tenant_id)
    assert allowed is True
    
    stats = throttler.get_tenant_stats(tenant_id)
    assert stats["active_streams"] == 1
    assert stats["total_streams"] == 1
    
    # Release stream
    await throttler.release_stream(tenant_id)
    
    stats = throttler.get_tenant_stats(tenant_id)
    assert stats["active_streams"] == 0
    
    logger.info("Stream release test passed")


@pytest.mark.asyncio
async def test_stream_peak_tracking():
    """
    Test that peak concurrent streams is tracked.
    
    Verifies that the peak concurrent streams counter tracks the maximum
    number of simultaneous streams and does not decrease when streams are released.
    """
    logger.info("Testing stream peak tracking")
    
    throttler = TenantThrottler(max_concurrent_streams_per_tenant=10)
    tenant_id = uuid4()
    
    # Acquire 3 streams
    for _ in range(3):
        await throttler.check_stream_limit(tenant_id)
    
    stats = throttler.get_tenant_stats(tenant_id)
    assert stats["peak_concurrent_streams"] == 3
    
    # Release 2 streams
    for _ in range(2):
        await throttler.release_stream(tenant_id)
    
    stats = throttler.get_tenant_stats(tenant_id)
    assert stats["peak_concurrent_streams"] == 3  # Peak should not decrease
    
    logger.info("Stream peak tracking test passed")


@pytest.mark.asyncio
async def test_reset_tenant():
    """
    Test resetting tenant throttling state.
    
    Verifies that resetting a tenant clears all counters and state.
    """
    logger.info("Testing tenant reset")
    
    throttler = TenantThrottler()
    tenant_id = uuid4()
    
    # Acquire some requests and streams
    await throttler.check_rate_limit(tenant_id)
    await throttler.check_stream_limit(tenant_id)
    
    stats = throttler.get_tenant_stats(tenant_id)
    assert stats["request_count"] == 1
    assert stats["active_streams"] == 1
    
    # Reset tenant
    throttler.reset_tenant(tenant_id)
    
    stats = throttler.get_tenant_stats(tenant_id)
    assert stats["request_count"] == 0
    assert stats["concurrent_requests"] == 0
    assert stats["active_streams"] == 0
    
    logger.info("Tenant reset test passed")


@pytest.mark.asyncio
async def test_global_throttler():
    """
    Test global throttler instance.
    
    Verifies that the global throttler singleton returns the same instance
    across multiple calls.
    """
    logger.info("Testing global throttler instance")
    
    throttler = get_throttler()
    
    assert throttler is not None
    assert isinstance(throttler, TenantThrottler)
    
    # Subsequent calls should return same instance
    throttler2 = get_throttler()
    assert throttler is throttler2
    
    logger.info("Global throttler instance test passed")


@pytest.mark.asyncio
async def test_multiple_tenant_isolation():
    """
    Test that different tenants have separate throttling state.
    
    Verifies that throttling state is isolated per tenant, so limits
    for one tenant do not affect another.
    """
    logger.info("Testing multiple tenant isolation")
    
    throttler = TenantThrottler(max_concurrent_requests=1)
    tenant_id_1 = uuid4()
    tenant_id_2 = uuid4()
    
    # Acquire request for tenant 1
    allowed, _ = await throttler.check_rate_limit(tenant_id_1)
    assert allowed is True
    
    # Tenant 2 should still be able to acquire request
    allowed, _ = await throttler.check_rate_limit(tenant_id_2)
    assert allowed is True
    
    stats_1 = throttler.get_tenant_stats(tenant_id_1)
    stats_2 = throttler.get_tenant_stats(tenant_id_2)
    
    assert stats_1["concurrent_requests"] == 1
    assert stats_2["concurrent_requests"] == 1
    
    logger.info("Multiple tenant isolation test passed")


@pytest.mark.asyncio
async def test_request_count_resets_after_window():
    """
    Test that request count resets after time window.
    
    Verifies that when the time window expires, the request count resets
    to allow new requests.
    """
    logger.info("Testing request count resets after time window")
    
    throttler = TenantThrottler(max_requests_per_minute=2)
    tenant_id = uuid4()
    
    # Use up the limit
    for _ in range(2):
        await throttler.check_rate_limit(tenant_id)
    
    stats = throttler.get_tenant_stats(tenant_id)
    assert stats["request_count"] == 2
    
    # Manually reset window_start to simulate time passing
    state = throttler._tenant_states[str(tenant_id)]
    state.window_start = time.time() - 70  # 70 seconds ago
    
    # Next request should reset count
    allowed, _ = await throttler.check_rate_limit(tenant_id)
    assert allowed is True
    
    stats = throttler.get_tenant_stats(tenant_id)
    assert stats["request_count"] == 1
    
    logger.info("Request count resets after time window test passed")
