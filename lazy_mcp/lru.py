"""LRU cache with pinning support for lazy_mcp."""

from collections import OrderedDict
from typing import Generic, TypeVar

from lazy_mcp.models import DEFAULT_LRU_CAPACITY

K = TypeVar("K")
V = TypeVar("V")


class LRUCache(Generic[K, V]):
    """Generic LRU cache using OrderedDict with pin support."""

    def __init__(self, capacity: int = DEFAULT_LRU_CAPACITY) -> None:
        self._capacity: int = capacity
        self._cache: OrderedDict[K, V] = OrderedDict()
        self._pinned: set[K] = set()
        self._hits: int = 0
        self._misses: int = 0

    def get(self, key: K) -> V | None:
        """Return cached value or None. Moves hit entry to end (most recent)."""
        if key in self._cache:
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None

    def put(self, key: K, value: V) -> None:
        """Insert or update a cache entry, evicting LRU unpinned if at capacity."""
        if key in self._cache:
            self._cache[key] = value
            self._cache.move_to_end(key)
            return

        if len(self._cache) >= self._capacity:
            # Find the LRU entry that is NOT pinned
            evicted = False
            for candidate_key in list(self._cache.keys()):
                if candidate_key not in self._pinned:
                    del self._cache[candidate_key]
                    evicted = True
                    break
            if not evicted:
                raise RuntimeError("LRU capacity exhausted — all entries pinned")

        self._cache[key] = value

    def evict(self, key: K) -> bool:
        """Remove from cache and pinned set. Returns True if removed."""
        if key in self._cache:
            del self._cache[key]
            self._pinned.discard(key)
            return True
        return False

    def pin(self, key: K) -> None:
        """Add to pinned set. Key does not need to be in cache."""
        self._pinned.add(key)

    def unpin(self, key: K) -> None:
        """Remove from pinned set. Silent if key not pinned."""
        self._pinned.discard(key)

    def stats(self) -> dict:
        """Return cache statistics."""
        total = self._hits + self._misses
        return {
            "capacity": self._capacity,
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "pinned": len(self._pinned),
            "hit_rate": self._hits / total if total > 0 else 0.0,
        }

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: K) -> bool:
        return key in self._cache
