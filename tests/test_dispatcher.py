# tests/test_dispatcher.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from lazy_mcp.dispatcher import Dispatcher
from lazy_mcp.registry import ToolRegistry
from lazy_mcp.models import HealthStatus
from lazy_mcp.errors import ServerOfflineError, DispatchError


@pytest.fixture
def registry():
    return ToolRegistry()


@pytest.fixture
def dispatcher(registry):
    return Dispatcher(registry, lru_capacity=4)


# THE test — catches the double-invoke
async def test_loader_called_exactly_once_with_correct_params(registry, dispatcher):
    loader = AsyncMock(return_value={"data": "result"})
    registry.register("srv", "tool", "a tool", loader)

    await dispatcher.dispatch("srv::tool", {"query": "hello"})

    loader.assert_called_once()                      # not twice
    loader.assert_called_once_with({"query": "hello"})  # with the real params


# corollary — second call also fires loader once, not zero times (no result caching)
async def test_loader_called_on_every_dispatch_not_cached(registry, dispatcher):
    loader = AsyncMock(return_value={"data": "result"})
    registry.register("srv", "tool", "a tool", loader)

    await dispatcher.dispatch("srv::tool", {"q": "first"})
    await dispatcher.dispatch("srv::tool", {"q": "second"})

    assert loader.call_count == 2
    calls = [c.args[0] for c in loader.call_args_list]
    assert {"q": "first"} in calls
    assert {"q": "second"} in calls


async def test_lru_warms_on_first_call_miss(registry, dispatcher):
    loader = AsyncMock(return_value={})
    registry.register("srv", "tool", "a tool", loader)

    stats_before = dispatcher._lru.stats()
    await dispatcher.dispatch("srv::tool", {})
    stats_after = dispatcher._lru.stats()

    assert stats_before["misses"] == 0
    assert stats_after["misses"] == 1   # cold path taken
    assert stats_after["size"] == 1     # now warmed


async def test_lru_hits_on_second_call(registry, dispatcher):
    loader = AsyncMock(return_value={})
    registry.register("srv", "tool", "a tool", loader)

    await dispatcher.dispatch("srv::tool", {})
    await dispatcher.dispatch("srv::tool", {})

    stats = dispatcher._lru.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1


async def test_dead_server_raises_before_loader(registry, dispatcher):
    loader = AsyncMock(return_value={})
    registry.register("srv", "tool", "a tool", loader)
    from lazy_mcp.models import DEFAULT_HEALTH_FAIL_LIMIT
    for _ in range(DEFAULT_HEALTH_FAIL_LIMIT):
        registry.update_health("srv", HealthStatus.COLD, increment_fail=True)

    with pytest.raises(ServerOfflineError):
        await dispatcher.dispatch("srv::tool", {})

    loader.assert_not_called()   # loader never reached


async def test_loader_exception_increments_fail_count(registry, dispatcher):
    loader = AsyncMock(side_effect=RuntimeError("boom"))
    registry.register("srv", "tool", "a tool", loader)

    with pytest.raises(DispatchError) as exc_info:
        await dispatcher.dispatch("srv::tool", {})

    assert exc_info.value.tool_key == "srv::tool"
    assert isinstance(exc_info.value.cause, RuntimeError)
    assert registry.get_health("srv").fail_count == 1


async def test_sync_loader_works(registry, dispatcher):
    # sync loaders should also fire exactly once
    loader = MagicMock(return_value={"sync": True})
    registry.register("srv", "sync_tool", "sync tool", loader)

    result = await dispatcher.dispatch("srv::sync_tool", {"x": 1})

    loader.assert_called_once_with({"x": 1})
    assert result.success is True
