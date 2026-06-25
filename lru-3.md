SHARED CONTEXT (paste above)

Write lazy_mcp/lru.py. Imports: collections.OrderedDict, typing only.

Write a generic class LRUCache[K, V] using OrderedDict internally.

Fields (private):
  _capacity: int
  _cache: OrderedDict
  _pinned: set[K]        # pinned keys are never evicted
  _hits: int
  _misses: int

Methods (exact signatures):
  __init__(self, capacity: int = DEFAULT_LRU_CAPACITY)
  get(self, key: K) -> V | None
    — on hit: move_to_end, increment _hits, return value
    — on miss: increment _misses, return None
  put(self, key: K, value: V) -> None
    — if key exists: update value, move_to_end
    — if at capacity: evict LRU that is NOT in _pinned, then insert
    — if all entries are pinned and at capacity: raise RuntimeError with 
      message "LRU capacity exhausted — all entries pinned"
  evict(self, key: K) -> bool
    — remove from cache and _pinned if present
    — return True if removed, False if key was not present
  pin(self, key: K) -> None
    — add to _pinned set. key does not need to be in cache.
  unpin(self, key: K) -> None
    — remove from _pinned. silent if key not pinned.
  stats(self) -> dict
    — return {"capacity": int, "size": int, "hits": int, 
               "misses": int, "pinned": int, 
               "hit_rate": float}   # hit_rate = hits/(hits+misses), 0.0 if both zero
  __len__(self) -> int
  __contains__(self, key: K) -> bool
