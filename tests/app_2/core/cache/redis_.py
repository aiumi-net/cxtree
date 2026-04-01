"""Redis-backed cache implementation."""

import json
from typing import Any

from core.cache.backend import CacheBackend


class RedisCache(CacheBackend):
    """Cache backend backed by Redis.

    Values are JSON-serialised before storage so arbitrary Python objects
    can be cached as long as they are JSON-serialisable.
    """

    def __init__(self, url: str) -> None:
        # Lazy import: redis is an optional dependency
        import redis as _redis  # ++

        self._client = _redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> Any | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        serialised = json.dumps(value)
        if ttl is not None:
            self._client.setex(key, ttl, serialised)
        else:
            self._client.set(key, serialised)

    def delete(self, key: str) -> bool:
        return bool(self._client.delete(key))

    def flush(self) -> None:
        self._client.flushdb()  # ---
