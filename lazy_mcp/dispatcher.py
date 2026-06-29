import asyncio
import inspect
from typing import Any

from lazy_mcp.models import DispatchResult, HealthStatus
from lazy_mcp.lru import LRUCache
from lazy_mcp.registry import ToolRegistry
from lazy_mcp.errors import (
    ServerOfflineError, PartialResultError, DispatchError, ToolNotFoundError
)
from lazy_mcp.models import DEFAULT_LRU_CAPACITY, STREAM_TIMEOUT_SECONDS


class Dispatcher:

    def __init__(self, registry: ToolRegistry,
                 lru_capacity: int = DEFAULT_LRU_CAPACITY):
        self._registry = registry
        self._lru: LRUCache = LRUCache(lru_capacity)

    async def dispatch(self, tool_key: str, params: dict) -> DispatchResult:
        # 1. existence check
        tool_entry = self._registry.get(tool_key)  # raises ToolNotFoundError if missing

        # 2. health gate — fail fast before any I/O
        server_name = tool_key.split("::")[0]
        health = self._registry.get_health(server_name)
        if health and health.status == HealthStatus.DEAD:
            raise ServerOfflineError(server_name)

        # 3. LRU: warm/cold tracking only — does NOT cache results
        warm = self._lru.get(tool_key)
        if not warm:
            self._ensure_warm(tool_key)   # marks LRU, no I/O

        # 4. invoke — single call to loader with real params
        try:
            result = await self._invoke(tool_entry, params)
            self._registry.update_health(server_name, HealthStatus.WARM)
            return DispatchResult(
                success=True, tool_key=tool_key,
                result=result, partial=False, error_msg=None
            )
        except PartialResultError as e:
            self._registry.update_health(
                server_name, HealthStatus.COLD, increment_fail=True
            )
            return DispatchResult(
                success=False, tool_key=tool_key,
                result=e.partial_result, partial=True, error_msg=str(e)
            )
        except Exception as e:
            self._registry.update_health(
                server_name, HealthStatus.COLD, increment_fail=True
            )
            raise DispatchError(cause=e, tool_key=tool_key)

    def _ensure_warm(self, tool_key: str) -> None:
        """Mark tool as warm in LRU. No loader call — warmth is connection state."""
        self._lru.put(tool_key, True)

    async def _invoke(self, tool_entry, params: dict) -> Any:
        """Single, authoritative call to the loader with real params."""
        loader = tool_entry.loader
        try:
            if inspect.iscoroutinefunction(loader):
                return await asyncio.wait_for(
                    loader(params),
                    timeout=STREAM_TIMEOUT_SECONDS
                )
            else:
                # sync loader — run in executor so we don't block the event loop
                loop = asyncio.get_running_loop()
                return await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: loader(params)),
                    timeout=STREAM_TIMEOUT_SECONDS
                )
        except asyncio.TimeoutError:
            raise PartialResultError(
                partial_result=None,
                message=f"{tool_entry.tool_key} timed out after {STREAM_TIMEOUT_SECONDS}s"
            )
