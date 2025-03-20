import time
from typing import Dict, Any, Optional, Tuple

from app.core.config import config

# In-memory cache storage
# Structure: {key: (value, timestamp, ttl)}
_cache: Dict[str, Tuple[Any, float, int]] = {}

# Last time the cache was cleaned up
_last_cleanup = time.time()


def get_cache(key: str) -> Optional[Any]:
    """
    Get a value from the cache.

    Args:
        key: Cache key

    Returns:
        Cached value or None if not found or expired
    """
    if not config.cache_enabled:
        return None

    if key not in _cache:
        return None

    value, timestamp, ttl = _cache[key]

    # Check if cache entry has expired
    if time.time() - timestamp > ttl:
        # Expired, remove from cache
        del _cache[key]
        return None

    # Periodically clean up expired entries
    _maybe_cleanup_cache()

    return value


def set_cache(key: str, value: Any, ttl: Optional[int] = None) -> None:
    """
    Set a value in the cache.

    Args:
        key: Cache key
        value: Value to cache
        ttl: Time to live in seconds (overrides global config)
    """
    if not config.cache_enabled:
        return

    # Use provided TTL or default from config
    _cache[key] = (value, time.time(), ttl or config.cache_ttl)


def clear_cache(key_prefix: Optional[str] = None) -> None:
    """
    Clear cache entries.

    Args:
        key_prefix: If provided, only clear keys starting with this prefix
    """
    global _cache

    if key_prefix:
        # Remove keys that start with the prefix
        keys_to_remove = [k for k in _cache if k.startswith(key_prefix)]
        for key in keys_to_remove:
            del _cache[key]
    else:
        # Clear entire cache
        _cache = {}


def _maybe_cleanup_cache() -> None:
    """
    Periodically clean up expired cache entries
    Only runs cleanup if it's been at least CLEANUP_INTERVAL seconds since last cleanup
    """
    global _last_cleanup

    # Run cleanup at most once per minute
    CLEANUP_INTERVAL = 60

    now = time.time()
    if now - _last_cleanup > CLEANUP_INTERVAL:
        # Find all expired keys
        expired_keys = []
        for key, (_, timestamp, ttl) in _cache.items():
            if now - timestamp > ttl:
                expired_keys.append(key)

        # Remove expired keys
        for key in expired_keys:
            del _cache[key]

        # Update last cleanup time
        _last_cleanup = now


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dictionary with cache statistics
    """
    if not _cache:
        return {
            "total_entries": 0,
            "expired_entries": 0,
            "memory_usage_estimate_kb": 0
        }

    now = time.time()
    expired_count = sum(1 for _, timestamp, ttl in _cache.values() if now - timestamp > ttl)

    # Rough estimate of memory usage (key size + value size)
    memory_usage = sum(
        len(key) + len(str(value))
        for key, (value, _, _) in _cache.items()
    )

    return {
        "total_entries": len(_cache),
        "expired_entries": expired_count,
        "memory_usage_estimate_kb": memory_usage / 1024
    }
