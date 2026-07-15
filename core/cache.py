import time
import os
import logging

logger = logging.getLogger(__name__)

class AppCache:
    def __init__(self):
        self._cache = {}

    def get(self, key, validator_func=None, ttl=None):
        """
        Retrieve a cached value.
        If ttl (in seconds) is provided, checks if cache has expired.
        If validator_func is provided, executes it and compares its return value
        with the cached validator state. If they differ, the cache is invalid.
        """
        entry = self._cache.get(key)
        if not entry:
            return None

        # Check TTL expiration
        if ttl is not None:
            if time.time() - entry["timestamp"] > ttl:
                logger.debug(f"Cache expired for key: {key} (TTL exceeded)")
                return None

        # Check Validator state
        if validator_func is not None:
            try:
                current_state = validator_func()
                if current_state != entry["validator_state"]:
                    logger.debug(f"Cache invalid for key: {key} (Validator state changed)")
                    return None
            except Exception as e:
                logger.warning(f"Error executing validator for cache key {key}: {e}")
                return None

        logger.debug(f"Cache HIT for key: {key}")
        return entry["value"]

    def set(self, key, value, validator_state=None):
        """
        Store a value in cache with optional validator state.
        """
        self._cache[key] = {
            "value": value,
            "timestamp": time.time(),
            "validator_state": validator_state
        }
        logger.debug(f"Cache SET for key: {key}")

    def invalidate(self, key):
        """
        Explicitly invalidate a cache key.
        """
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache invalidated for key: {key}")

    def clear(self):
        """
        Clear all cache entries.
        """
        self._cache.clear()
        logger.debug("Cache cleared")

# Global Cache Instance
cache_manager = AppCache()
