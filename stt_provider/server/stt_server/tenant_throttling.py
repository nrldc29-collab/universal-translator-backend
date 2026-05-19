"""
Tenant throttling module for request and stream rate limiting.

This module provides functionality for throttling requests and streams per tenant
to prevent abuse and ensure fair resource allocation. It supports per-second,
per-minute, and concurrent request limits, as well as concurrent stream limits.
"""
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class TenantRequestState:
    """
    Track request state for a tenant.
    
    Maintains request counting and timing information for rate limiting
    calculations.
    
    Attributes:
        request_count: Number of requests in the current time window
        window_start: Timestamp when the current time window started
        last_request_time: Timestamp of the last request
    """
    request_count: int = 0
    window_start: float = 0.0
    last_request_time: float = 0.0


@dataclass
class TenantStreamState:
    """
    Track streaming state for a tenant.
    
    Maintains stream counting and peak concurrency information for
    stream limit calculations.
    
    Attributes:
        active_streams: Current number of active streams
        total_streams: Total number of streams initiated
        peak_concurrent_streams: Peak number of concurrent streams
    """
    active_streams: int = 0
    total_streams: int = 0
    peak_concurrent_streams: int = 0


class TenantThrottler:
    """
    Throttle requests per tenant to prevent abuse.
    
    Provides rate limiting for both REST requests and WebSocket streams,
    with configurable limits for per-second, per-minute, and concurrent
    requests, as well as concurrent streams per tenant.
    
    Attributes:
        max_requests_per_second: Maximum requests allowed per second
        max_requests_per_minute: Maximum requests allowed per minute
        max_concurrent_requests: Maximum concurrent requests
        max_concurrent_streams_per_tenant: Maximum concurrent streams per tenant
        _tenant_states: Dictionary mapping tenant IDs to request states
        _concurrent_requests: Dictionary mapping tenant IDs to concurrent request counts
        _stream_states: Dictionary mapping tenant IDs to stream states
    """
    
    def __init__(
        self,
        max_requests_per_second: int = 10,
        max_requests_per_minute: int = 100,
        max_concurrent_requests: int = 5,
        max_concurrent_streams_per_tenant: int = 10,
    ) -> None:
        """
        Initialize the tenant throttler.
        
        Args:
            max_requests_per_second: Maximum requests per second (default: 10)
            max_requests_per_minute: Maximum requests per minute (default: 100)
            max_concurrent_requests: Maximum concurrent requests (default: 5)
            max_concurrent_streams_per_tenant: Maximum concurrent streams per tenant (default: 10)
        """
        self.max_requests_per_second = max_requests_per_second
        self.max_requests_per_minute = max_requests_per_minute
        self.max_concurrent_requests = max_concurrent_requests
        self.max_concurrent_streams_per_tenant = max_concurrent_streams_per_tenant
        self._tenant_states: Dict[str, TenantRequestState] = {}
        self._concurrent_requests: Dict[str, int] = {}
        self._stream_states: Dict[str, TenantStreamState] = {}
        logger.info(
            f"TenantThrottler initialized with max_requests_per_second={max_requests_per_second}, "
            f"max_requests_per_minute={max_requests_per_minute}, "
            f"max_concurrent_requests={max_concurrent_requests}, "
            f"max_concurrent_streams_per_tenant={max_concurrent_streams_per_tenant}"
        )
    
    async def check_rate_limit(
        self,
        tenant_id: UUID,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if tenant is within rate limits.
        
        Evaluates per-second, per-minute, and concurrent request limits
        for the specified tenant. Initializes state if not already present.
        
        Args:
            tenant_id: Tenant UUID
            
        Returns:
            Tuple of (allowed, error_message) where allowed is True if request is permitted
        """
        tenant_key = str(tenant_id)
        now = time.time()
        
        # Initialize state if not exists
        if tenant_key not in self._tenant_states:
            self._tenant_states[tenant_key] = TenantRequestState(
                window_start=now,
                last_request_time=now,
            )
            self._concurrent_requests[tenant_key] = 0
            logger.debug(
                "Initialized throttling state for tenant",
                extra={"tenant_id": tenant_key},
            )
        
        state = self._tenant_states[tenant_key]
        
        # Reset counters if window expired (1 minute)
        if now - state.window_start > 60:
            logger.debug(
                "Resetting rate limit window for tenant",
                extra={
                    "tenant_id": tenant_key,
                    "previous_count": state.request_count,
                },
            )
            state.request_count = 0
            state.window_start = now
        
        # Check per-second rate limit
        if now - state.last_request_time < (1.0 / self.max_requests_per_second):
            logger.warning(
                "Per-second rate limit exceeded for tenant",
                extra={
                    "tenant_id": tenant_key,
                    "limit": self.max_requests_per_second,
                },
            )
            return False, f"Rate limit exceeded: max {self.max_requests_per_second} requests per second"
        
        # Check per-minute rate limit
        if state.request_count >= self.max_requests_per_minute:
            logger.warning(
                "Per-minute rate limit exceeded for tenant",
                extra={
                    "tenant_id": tenant_key,
                    "limit": self.max_requests_per_minute,
                    "current_count": state.request_count,
                },
            )
            return False, f"Rate limit exceeded: max {self.max_requests_per_minute} requests per minute"
        
        # Check concurrent request limit
        if self._concurrent_requests[tenant_key] >= self.max_concurrent_requests:
            logger.warning(
                "Concurrent request limit exceeded for tenant",
                extra={
                    "tenant_id": tenant_key,
                    "limit": self.max_concurrent_requests,
                    "current_concurrent": self._concurrent_requests[tenant_key],
                },
            )
            return False, f"Concurrent request limit exceeded: max {self.max_concurrent_requests} concurrent requests"
        
        # Update state
        state.request_count += 1
        state.last_request_time = now
        self._concurrent_requests[tenant_key] += 1
        
        logger.debug(
            "Request allowed for tenant",
            extra={
                "tenant_id": tenant_key,
                "request_count": state.request_count,
                "concurrent_requests": self._concurrent_requests[tenant_key],
            },
        )
        
        return True, None
    
    async def check_stream_limit(
        self,
        tenant_id: UUID,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if tenant can start a new stream.
        
        Evaluates concurrent stream limits for the specified tenant.
        Initializes stream state if not already present.
        
        Args:
            tenant_id: Tenant UUID
            
        Returns:
            Tuple of (allowed, error_message) where allowed is True if stream is permitted
        """
        tenant_key = str(tenant_id)
        
        # Initialize stream state if not exists
        if tenant_key not in self._stream_states:
            self._stream_states[tenant_key] = TenantStreamState()
            logger.debug(
                "Initialized stream state for tenant",
                extra={"tenant_id": tenant_key},
            )
        
        stream_state = self._stream_states[tenant_key]
        
        # Check concurrent stream limit
        if stream_state.active_streams >= self.max_concurrent_streams_per_tenant:
            logger.warning(
                "Concurrent stream limit exceeded for tenant",
                extra={
                    "tenant_id": tenant_key,
                    "limit": self.max_concurrent_streams_per_tenant,
                    "current_streams": stream_state.active_streams,
                },
            )
            return False, f"Concurrent stream limit exceeded: max {self.max_concurrent_streams_per_tenant} concurrent streams per tenant"
        
        # Increment stream count
        stream_state.active_streams += 1
        stream_state.total_streams += 1
        stream_state.peak_concurrent_streams = max(
            stream_state.peak_concurrent_streams,
            stream_state.active_streams,
        )
        
        logger.info(
            "Stream started for tenant",
            extra={
                "tenant_id": tenant_key,
                "active_streams": stream_state.active_streams,
                "total_streams": stream_state.total_streams,
                "peak_streams": stream_state.peak_concurrent_streams,
            },
        )
        
        return True, None
    
    async def release_request(self, tenant_id: UUID) -> None:
        """
        Release a request from concurrent count.
        
        Decrements the concurrent request counter for the specified tenant
        when a request completes.
        
        Args:
            tenant_id: Tenant UUID
        """
        tenant_key = str(tenant_id)
        if tenant_key in self._concurrent_requests:
            self._concurrent_requests[tenant_key] = max(
                0,
                self._concurrent_requests[tenant_key] - 1,
            )
            logger.debug(
                "Request released for tenant",
                extra={
                    "tenant_id": tenant_key,
                    "concurrent_requests": self._concurrent_requests[tenant_key],
                },
            )
    
    async def release_stream(self, tenant_id: UUID) -> None:
        """
        Release a stream from concurrent count.
        
        Decrements the active stream counter for the specified tenant
        when a stream closes.
        
        Args:
            tenant_id: Tenant UUID
        """
        tenant_key = str(tenant_id)
        if tenant_key in self._stream_states:
            stream_state = self._stream_states[tenant_key]
            stream_state.active_streams = max(0, stream_state.active_streams - 1)
            logger.debug(
                "Stream released for tenant",
                extra={
                    "tenant_id": tenant_key,
                    "active_streams": stream_state.active_streams,
                },
            )
    
    def get_tenant_stats(self, tenant_id: UUID) -> Dict[str, int]:
        """
        Get current stats for a tenant.
        
        Returns current throttling statistics for the specified tenant,
        including request counts, stream counts, and timing information.
        
        Args:
            tenant_id: Tenant UUID
            
        Returns:
            Dictionary containing tenant throttling statistics
        """
        tenant_key = str(tenant_id)
        state = self._tenant_states.get(tenant_key)
        stream_state = self._stream_states.get(tenant_key)
        
        return {
            "request_count": state.request_count if state else 0,
            "concurrent_requests": self._concurrent_requests.get(tenant_key, 0),
            "window_start": int(state.window_start) if state else 0,
            "last_request_time": int(state.last_request_time) if state else 0,
            "active_streams": stream_state.active_streams if stream_state else 0,
            "total_streams": stream_state.total_streams if stream_state else 0,
            "peak_concurrent_streams": stream_state.peak_concurrent_streams if stream_state else 0,
        }
    
    def reset_tenant(self, tenant_id: UUID) -> None:
        """
        Reset throttling state for a tenant.
        
        Clears all throttling state for the specified tenant, allowing
        them to start fresh with rate limits.
        
        Args:
            tenant_id: Tenant UUID
        """
        tenant_key = str(tenant_id)
        if tenant_key in self._tenant_states:
            del self._tenant_states[tenant_key]
        if tenant_key in self._concurrent_requests:
            del self._concurrent_requests[tenant_key]
        if tenant_key in self._stream_states:
            del self._stream_states[tenant_key]
        logger.info(f"Reset throttling state for tenant {tenant_key}")


# Global throttler instance
_global_throttler = TenantThrottler()


def get_throttler() -> TenantThrottler:
    """
    Get the global tenant throttler instance.
    
    Returns the singleton throttler instance for use across the application.
    
    Returns:
        Global TenantThrottler instance
    """
    return _global_throttler
