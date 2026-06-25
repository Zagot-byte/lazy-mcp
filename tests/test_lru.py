"""Tests for lazy_mcp.lru — LRU cache with pinning."""

import pytest

from lazy_mcp.lru import LRUCache


# ── Basic operations ───────────────────────────────────────────────────────────

def test_put_and_get():
    c = LRUCache(capacity=4)
    c.put("a", 1)
    assert c.get("a") == 1


def test_get_miss_returns_none():
    c = LRUCache(capacity=4)
    assert c.get("nope") is None


def test_put_overwrites():
    c = LRUCache(capacity=4)
    c.put("a", 1)
    c.put("a", 2)
    assert c.get("a") == 2
    assert len(c) == 1


def test_contains():
    c = LRUCache(capacity=4)
    c.put("a", 1)
    assert "a" in c
    assert "b" not in c


def test_len():
    c = LRUCache(capacity=4)
    assert len(c) == 0
    c.put("a", 1)
    c.put("b", 2)
    assert len(c) == 2


# ── Eviction ───────────────────────────────────────────────────────────────────

def test_evicts_lru_when_at_capacity():
    c = LRUCache(capacity=3)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    c.put("d", 4)  # should evict "a"
    assert c.get("a") is None
    assert c.get("d") == 4
    assert len(c) == 3


def test_access_refreshes_lru_order():
    c = LRUCache(capacity=3)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    c.get("a")     # "a" is now most recent
    c.put("d", 4)  # should evict "b" (oldest untouched)
    assert c.get("a") == 1
    assert c.get("b") is None


def test_manual_evict():
    c = LRUCache(capacity=4)
    c.put("a", 1)
    assert c.evict("a") is True
    assert c.get("a") is None
    assert len(c) == 0


def test_evict_nonexistent_returns_false():
    c = LRUCache(capacity=4)
    assert c.evict("nope") is False


# ── Pinning ────────────────────────────────────────────────────────────────────

def test_pinned_not_evicted():
    c = LRUCache(capacity=3)
    c.put("a", 1)
    c.pin("a")
    c.put("b", 2)
    c.put("c", 3)
    c.put("d", 4)  # evicts "b" (oldest unpinned), not "a"
    assert c.get("a") == 1
    assert c.get("b") is None


def test_all_pinned_raises():
    c = LRUCache(capacity=2)
    c.put("a", 1)
    c.put("b", 2)
    c.pin("a")
    c.pin("b")
    with pytest.raises(RuntimeError, match="all entries pinned"):
        c.put("c", 3)


def test_unpin_allows_eviction():
    c = LRUCache(capacity=2)
    c.put("a", 1)
    c.put("b", 2)
    c.pin("a")
    c.pin("b")
    c.unpin("a")
    c.put("c", 3)  # should evict "a" now
    assert c.get("a") is None
    assert c.get("b") == 2
    assert c.get("c") == 3


def test_pin_key_not_in_cache():
    c = LRUCache(capacity=4)
    c.pin("future_key")  # should not raise


def test_unpin_key_not_pinned():
    c = LRUCache(capacity=4)
    c.unpin("nope")  # should not raise


def test_evict_removes_from_pinned():
    c = LRUCache(capacity=4)
    c.put("a", 1)
    c.pin("a")
    c.evict("a")
    assert "a" not in c


# ── Stats ──────────────────────────────────────────────────────────────────────

def test_stats_initial():
    c = LRUCache(capacity=16)
    s = c.stats()
    assert s["capacity"] == 16
    assert s["size"] == 0
    assert s["hits"] == 0
    assert s["misses"] == 0
    assert s["pinned"] == 0
    assert s["hit_rate"] == 0.0


def test_stats_after_operations():
    c = LRUCache(capacity=8)
    c.put("a", 1)
    c.pin("a")
    c.get("a")     # hit
    c.get("a")     # hit
    c.get("nope")  # miss
    s = c.stats()
    assert s["size"] == 1
    assert s["hits"] == 2
    assert s["misses"] == 1
    assert s["pinned"] == 1
    assert s["hit_rate"] == pytest.approx(2 / 3)


def test_hit_rate_zero_when_no_access():
    c = LRUCache(capacity=4)
    assert c.stats()["hit_rate"] == 0.0
