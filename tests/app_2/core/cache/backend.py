"""Abstract cache backend interface."""

from abc import ABC, abstractmethod
from typing import Any


class CacheBackend(ABC):
    """Abstract base class for cache backends.

    All implementations must be thread-safe. Keys and values are strings
    unless otherwise noted.
    """

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Return the cached value for key, or None if absent or expired."""

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store value under key. ttl is seconds until expiry, or None = no expiry."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Remove key. Returns True if the key existed."""

    @abstractmethod
    def flush(self) -> None:
        """Remove all entries from the cache."""

    def get_or_set(self, key: str, default_fn, ttl: int | None = None) -> Any:
        """Return cached value or call default_fn(), store and return its result."""
        val = self.get(key)
        if val is None:
            val = default_fn()
            self.set(key, val, ttl)
        return val


class InMemoryCache(CacheBackend):
    """Simple in-memory cache with no TTL support (for testing)."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._store.get(key)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self._store[key] = value

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def flush(self) -> None:
        self._store.clear()
