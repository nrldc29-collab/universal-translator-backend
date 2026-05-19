"""
In-memory response cache for API responses.

This module provides a simple in-memory caching system for API responses
to reduce redundant processing and improve performance. Features include:
- Time-to-live (TTL) based expiration
- Decorator-based caching for async functions
- Cache statistics and cleanup utilities
- MD5-based key generation for consistent hashing
"""
import hashlib
import json
import logging
import time
from typing import Any, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)


class ResponseCache:
    """Simple in-memory response cache for API responses."""
    
    def __init__(self, default_ttl: int = 300):  # 5 minutes default
        self._cache: dict[str, dict] = {}
        self.default_ttl = default_ttl
    
    def _generate_key(self, prefix: str, **kwargs: Any) -> str:
        """Generate a cache key from prefix and kwargs."""
        key_parts = [prefix]
        
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}={v}")
        
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if it exists and hasn't expired."""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        
        # Check if expired
        if time.time() > entry["expires_at"]:
            del self._cache[key]
            return None
        
        return entry["value"]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Cache a value with optional TTL."""
        if ttl is None:
            ttl = self.default_ttl
        
        self._cache[key] = {
            "value": value,
            "expires_at": time.time() + ttl,
            "created_at": time.time(),
        }
    
    def delete(self, key: str) -> bool:
        """Delete a cached value."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if current_time > entry["expires_at"]
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        return len(expired_keys)
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        current_time = time.time()
        total_entries = len(self._cache)
        expired_entries = sum(
            1 for entry in self._cache.values()
            if current_time > entry["expires_at"]
        )
        
        return {
            "total_entries": total_entries,
            "active_entries": total_entries - expired_entries,
            "expired_entries": expired_entries,
            "default_ttl": self.default_ttl,
        }


# Global cache instance
_global_cache = ResponseCache()


def cache_response(prefix: str, ttl: Optional[int] = None):
    """
    Decorator to cache function responses.
    
    Automatically caches the return value of async functions based on
    their keyword arguments. Uses the global cache instance.
    
    Args:
        prefix: Prefix for cache key generation
        ttl: Time to live in seconds (uses default if not specified)
        
    Returns:
        Decorator function that can be applied to async functions
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = _global_cache._generate_key(prefix, **kwargs)
            
            # Try to get from cache
            cached_value = _global_cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_value
            
            # Execute function
            logger.debug(f"Cache miss for {func.__name__}, executing function")
            result = await func(*args, **kwargs)
            
            # Cache result
            _global_cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


def get_cache() -> ResponseCache:
    """
    Get the global response cache instance.
    
    Returns:
        The global ResponseCache singleton instance
    """
    return _global_cache


def invalidate_cache_pattern(prefix: str) -> int:
    """
    Invalidate all cache entries matching a pattern.
    
    Note: Since MD5 hashing is used for keys, pattern matching is not
    directly supported. This implementation clears all entries as a
    simplified approach. A production implementation would maintain
    a prefix index for selective invalidation.
    
    Args:
        prefix: Prefix pattern to match (currently ignored, clears all)
        
    Returns:
        Number of entries invalidated
    """
    count = len(_global_cache._cache)
    _global_cache.clear()
    logger.info(f"Invalidated {count} cache entries (pattern-based clearing)")
    return count
