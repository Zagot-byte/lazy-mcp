"""Tests for lazy_mcp.registry — tool registration and health tracking."""

import pytest
from unittest.mock import MagicMock

from lazy_mcp.registry import ToolRegistry
from lazy_mcp.models import HealthStatus, DEFAULT_HEALTH_FAIL_LIMIT
from lazy_mcp.errors import ToolNotFoundError


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_register_and_get():
    registry = ToolRegistry()
    loader = MagicMock()
    key = registry.register("brave", "search", "web search", loader)
    assert key == "brave::search"
    entry = registry.get("brave::search")
    assert entry.tool_key == "brave::search"
    assert entry.server_name == "brave"
    assert entry.tool_name == "search"
    assert entry.description == "web search"


def test_get_nonexistent_raises():
    registry = ToolRegistry()
    with pytest.raises(ToolNotFoundError):
        registry.get("brave::search")


def test_register_creates_server_health():
    registry = ToolRegistry()
    registry.register("brave", "search", "web search", MagicMock())
    health = registry.get_health("brave")
    assert health is not None
    assert health.status == HealthStatus.COLD
    assert health.fail_count == 0


def test_register_same_server_twice_no_duplicate_health():
    registry = ToolRegistry()
    registry.register("brave", "search", "web search", MagicMock())
    registry.register("brave", "images", "image search", MagicMock())
    health = registry.get_health("brave")
    assert health.fail_count == 0  # still one health entry, not doubled


def test_re_registration_overwrites_silently():
    registry = ToolRegistry()
    loader1 = MagicMock()
    loader2 = MagicMock()
    registry.register("brave", "search", "old description", loader1)
    registry.register("brave", "search", "new description", loader2)
    entry = registry.get("brave::search")
    assert entry.description == "new description"


def test_update_health_warm():
    registry = ToolRegistry()
    registry.register("brave", "search", "web search", MagicMock())
    registry.update_health("brave", HealthStatus.WARM)
    assert registry.get_health("brave").status == HealthStatus.WARM


def test_fail_count_increments():
    registry = ToolRegistry()
    registry.register("brave", "search", "web search", MagicMock())
    registry.update_health("brave", HealthStatus.COLD, increment_fail=True)
    registry.update_health("brave", HealthStatus.COLD, increment_fail=True)
    assert registry.get_health("brave").fail_count == 2


def test_dead_after_fail_limit():
    registry = ToolRegistry()
    registry.register("brave", "search", "web search", MagicMock())
    for _ in range(DEFAULT_HEALTH_FAIL_LIMIT):
        registry.update_health("brave", HealthStatus.COLD, increment_fail=True)
    assert registry.get_health("brave").status == HealthStatus.DEAD


def test_reset_health():
    registry = ToolRegistry()
    registry.register("brave", "search", "web search", MagicMock())
    for _ in range(DEFAULT_HEALTH_FAIL_LIMIT):
        registry.update_health("brave", HealthStatus.COLD, increment_fail=True)
    registry.reset_health("brave")
    health = registry.get_health("brave")
    assert health.status == HealthStatus.COLD
    assert health.fail_count == 0


def test_all_tools():
    registry = ToolRegistry()
    registry.register("brave", "search", "web search", MagicMock())
    registry.register("filesystem", "read_file", "read file", MagicMock())
    tools = registry.all_tools()
    assert len(tools) == 2


def test_tools_for_server():
    registry = ToolRegistry()
    registry.register("brave", "search", "web search", MagicMock())
    registry.register("brave", "images", "image search", MagicMock())
    registry.register("filesystem", "read_file", "read file", MagicMock())
    brave_tools = registry.tools_for_server("brave")
    assert len(brave_tools) == 2
    assert all(t.server_name == "brave" for t in brave_tools)
