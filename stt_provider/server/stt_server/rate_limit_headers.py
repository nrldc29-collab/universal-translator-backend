"""
Rate limit headers for HTTP responses.

This module provides functions to add rate limit information to HTTP response headers.
It supports both general API rate limiting headers and tenant-specific rate limit headers,
allowing clients to monitor their usage and respect rate limits.

Functions:
    add_rate_limit_headers: Add standard rate limit headers to responses.
    add_tenant_rate_limit_headers: Add tenant-specific rate limit headers to responses.

Usage:
    Use these functions in FastAPI endpoint handlers or middleware to provide
    rate limit information to API clients via response headers.
"""
import logging

from fastapi import Request, Response
from slowapi import Limiter

logger = logging.getLogger(__name__)


def add_rate_limit_headers(
    response: Response,
    limiter: Limiter,
    request: Request,
    key: str,
) -> None:
    """
    Add rate limit headers to HTTP responses.
    
    Extracts rate limit information from the slowapi limiter and adds
    standard rate limit headers to the response. Headers include:
    - X-RateLimit-Limit: Maximum requests allowed in the time window.
    - X-RateLimit-Remaining: Remaining requests in the current window.
    - X-RateLimit-Reset: Approximate Unix timestamp when limit resets.
    - X-RateLimit-Window: Time window in seconds (default 60).
    
    Args:
        response: FastAPI Response object to add headers to.
        limiter: slowapi Limiter instance with rate limit state.
        request: FastAPI Request object.
        key: Rate limit key used to identify the client.
    """
    try:
        # Get current rate limit state from slowapi
        if hasattr(limiter, "_storage"):
            storage = limiter._storage
            current_key = key
            
            # Try to get current count
            if hasattr(storage, "get"):
                current_count = storage.get(current_key)
                if current_count:
                    # Determine limit based on limiter configuration
                    limit = getattr(limiter, "_default_limits", [100])[0] if hasattr(limiter, "_default_limits") else 100
                    remaining = max(0, limit - int(current_count))
                    
                    # Add headers
                    response.headers["X-RateLimit-Limit"] = str(limit)
                    response.headers["X-RateLimit-Remaining"] = str(remaining)
                    response.headers["X-RateLimit-Window"] = "60"  # 1 minute window
                    response.headers["X-RateLimit-Reset"] = str(int(current_count * 60))  # Approximate reset time
                    
                    logger.debug(f"Rate limit headers added: limit={limit}, remaining={remaining}, key={key}")
    except Exception as e:
        # Don't fail if rate limit headers can't be added
        logger.warning(f"Failed to add rate limit headers: {e}")


def add_tenant_rate_limit_headers(
    response: Response,
    tenant_stats: dict,
) -> None:
    """
    Add tenant-specific rate limit headers.
    
    Adds tenant-specific rate limit and stream limit headers to the response,
    providing visibility into tenant-specific usage limits. Headers include:
    - X-Tenant-RateLimit-Limit: Maximum requests per minute for the tenant.
    - X-Tenant-RateLimit-Remaining: Remaining requests in current window.
    - X-Tenant-RateLimit-Used: Requests used in current window.
    - X-Tenant-ConcurrentStreams-Active: Current active stream count.
    - X-Tenant-ConcurrentStreams-Max: Maximum concurrent streams allowed.
    
    Args:
        response: FastAPI Response object to add headers to.
        tenant_stats: Dictionary containing tenant usage statistics with keys:
            - request_count: Number of requests in current window.
            - active_streams: Number of currently active streams.
    """
    try:
        request_count = tenant_stats.get("request_count", 0)
        concurrent_streams = tenant_stats.get("active_streams", 0)
        
        # Add tenant-specific headers
        response.headers["X-Tenant-RateLimit-Used"] = str(request_count)
        response.headers["X-Tenant-ConcurrentStreams-Active"] = str(concurrent_streams)
        
        # These would be configured based on tenant settings
        response.headers["X-Tenant-RateLimit-Limit"] = "100"
        response.headers["X-Tenant-RateLimit-Remaining"] = str(max(0, 100 - request_count))
        response.headers["X-Tenant-ConcurrentStreams-Max"] = "10"
        
        logger.debug(f"Tenant rate limit headers added: requests={request_count}, streams={concurrent_streams}")
    except Exception as e:
        # Don't fail if tenant headers can't be added
        logger.warning(f"Failed to add tenant rate limit headers: {e}")
