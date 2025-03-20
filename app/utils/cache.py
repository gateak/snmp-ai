import time
from typing import Dict, Any, Optional, Tuple

from app.core.config import config

# In-memory cache storage
# Structure: {key: (value, timestamp)}
_cache: Dict[str, Tuple[Any, float]] = {}


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

    value, timestamp = _cache[key]

    # Check if cache entry has expired
    if time.time() - timestamp > config.cache_ttl:
        # Expired, remove from cache
        del _cache[key]
        return None

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
    _cache[key] = (value, time.time())


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
