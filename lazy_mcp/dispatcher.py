"""Async tool dispatcher for lazy_mcp."""

import asyncio
import inspect
from typing import Any

from lazy_mcp.models import (
    DEFAULT_LRU_CAPACITY,
    STREAM_TIMEOUT_SECONDS,
    DispatchResult,
    HealthStatus,
)
from lazy_mcp.lru import LRUCache
from lazy_mcp.registry import ToolRegistry
from lazy_mcp.errors import (
    DispatchError,
    PartialResultError,
    ServerOfflineError,
    ToolNotFoundError,
)


class Dispatcher:
    """Dispatches tool calls with LRU caching and health tracking."""

    def __init__(
        self,
        registry: ToolRegistry,
        lru_capacity: int = DEFAULT_LRU_CAPACITY,
    ) -> None:
        self._lru: LRUCache = LRUCache(capacity=lru_capacity)
        self._registry: ToolRegistry = registry

    async def dispatch(self, tool_key: str, params: dict) -> DispatchResult:
        """
        Main dispatch flow:
        1. Lookup tool in registry (raises ToolNotFoundError if missing).
        2. Check server health — raise ServerOfflineError if DEAD.
        3. Load schema from LRU cache or cold-load.
        4. Invoke tool and handle errors.
        """
        # 1. Lookup
        tool_entry = self._registry.get(tool_key)

        # 2. Health check
        server_name = tool_key.split("::")[0]
        health = self._registry.get_health(server_name)
        if health is not None and health.status == HealthStatus.DEAD:
            raise ServerOfflineError(f"Server is offline: {server_name}")

        # 3. LRU cache check
        cached = self._lru.get(tool_key)
        if cached is None:
            await self._load_schema(tool_entry)

        # 4. Invoke
        try:
            result = await self._invoke(tool_entry, params)
            self._registry.update_health(server_name, HealthStatus.WARM)
            return DispatchResult(
                success=True,
                tool_key=tool_key,
                result=result,
                partial=False,
                error_msg=None,
            )
        except PartialResultError as e:
            self._registry.update_health(
                server_name, HealthStatus.COLD, increment_fail=True
            )
            return DispatchResult(
                success=False,
                tool_key=tool_key,
                result=e.partial_result,
                partial=True,
                error_msg=str(e),
            )
        except Exception as e:
            self._registry.update_health(
                server_name, HealthStatus.COLD, increment_fail=True
            )
            raise DispatchError(cause=e, tool_key=tool_key)

    async def _load_schema(self, tool_entry: Any) -> Any:
        """
        Call tool_entry.loader(). Await if it's a coroutine function.
        Store result in LRU under tool_entry.tool_key.
        """
        if inspect.iscoroutinefunction(tool_entry.loader):
            result = await tool_entry.loader()
        else:
            result = tool_entry.loader()
        self._lru.put(tool_entry.tool_key, result)
        return result

    async def _invoke(self, tool_entry: Any, params: dict) -> Any:
        """
        Call the loader with params, wrapped in asyncio.wait_for
        with STREAM_TIMEOUT_SECONDS timeout.
        """
        if inspect.iscoroutinefunction(tool_entry.loader):
            coro = tool_entry.loader(params)
        else:
            # Sync loader — wrap in a coroutine
            async def _sync_wrapper() -> Any:
                return tool_entry.loader(params)
            coro = _sync_wrapper()

        try:
            return await asyncio.wait_for(coro, timeout=STREAM_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            raise PartialResultError(
                partial_result=None,
                message=f"{tool_entry.tool_key} timed out after {STREAM_TIMEOUT_SECONDS}s",
            )
