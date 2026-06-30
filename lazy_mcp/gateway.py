"""LazyMCP gateway — the only class an external caller ever touches."""

from typing import Any, Callable

from lazy_mcp.models import (
    DEFAULT_LRU_CAPACITY,
    DEFAULT_MATCH_THRESHOLD,
    DispatchResult,
    HealthStatus,
    MatchResult,
)
from lazy_mcp.registry import ToolRegistry
from lazy_mcp.matcher import Matcher
from lazy_mcp.dispatcher import Dispatcher
from lazy_mcp.errors import (
    DispatchError,
    NoMatchError,
    ServerOfflineError,
    ToolNotFoundError,
)
from lazy_mcp.mcp_compat import MCPConnection, discover


class LazyMCP:
    """
    The single entry point for lazy_mcp.
    All other classes are internal implementation details.
    """

    def __init__(
        self,
        lru_capacity: int = DEFAULT_LRU_CAPACITY,
        match_threshold: float = DEFAULT_MATCH_THRESHOLD,
        semantic_hook: Callable | None = None,
    ) -> None:
        self._registry: ToolRegistry = ToolRegistry()
        self._matcher: Matcher = Matcher(
            threshold=match_threshold, semantic_hook=semantic_hook
        )
        self._dispatcher: Dispatcher = Dispatcher(
            registry=self._registry, lru_capacity=lru_capacity
        )
        self._connections: dict[str, MCPConnection] = {}

    def capabilities(self) -> list[str]:
        """Delegates to self._registry.list_capabilities(). 
        This is what gets shown to the LLM — never tool names or schemas."""
        return self._registry.list_capabilities()

    def register(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        loader: Callable,
        tags: list[str] = [],
        capabilities: list[str] = [],
        pinned: bool = False,
    ) -> str:
        """
        Delegates to _registry.register(...).
        If pinned=True: pin the tool_key in the LRU cache.
        Returns tool_key.
        """
        tool_key = self._registry.register(
            server_name=server_name,
            tool_name=tool_name,
            description=description,
            loader=loader,
            tags=tags,
            capabilities=capabilities,
        )
        if pinned:
            self._dispatcher._lru.pin(tool_key)
        return tool_key

    async def ask(
        self,
        capability: str,
        task: str,
        params: dict = {},
    ) -> DispatchResult:
        """
        1. tools = _registry.all_tools()
        2. matches = _matcher.match(capability, task, tools)
           On NoMatchError: return DispatchResult(success=False, tool_key="",
             result=None, partial=False, 
             error_msg=f"no tool for capability '{capability}'")
        3. best = matches[0]
        4. result = await _dispatcher.dispatch(best.tool_key, params)
        5. return result
        """
        tools = self._registry.all_tools()
        try:
            matches = self._matcher.match(capability, task, tools)
        except NoMatchError:
            return DispatchResult(
                success=False,
                tool_key="",
                result=None,
                partial=False,
                error_msg=f"no tool for capability '{capability}'",
            )
        best = matches[0]
        result = await self._dispatcher.dispatch(best.tool_key, params)
        return result

    def available(self, capability: str, task: str) -> list[MatchResult]:
        """
        Dry-run match — returns candidates without dispatching.
        Returns [] on NoMatchError (don't raise here).
        """
        tools = self._registry.all_tools()
        try:
            return self._matcher.match(capability, task, tools)
        except NoMatchError:
            return []

    def health(self) -> dict:
        """
        Return a summary dict with total tools, per-server health, and cache stats.
        """
        all_tools = self._registry.all_tools()
        servers: dict[str, dict] = {}
        seen_servers: set[str] = set()
        for tool in all_tools:
            seen_servers.add(tool.server_name)
        for server_name in seen_servers:
            health = self._registry.get_health(server_name)
            server_tools = self._registry.tools_for_server(server_name)
            servers[server_name] = {
                "status": health.status.value if health else "unknown",
                "fail_count": health.fail_count if health else 0,
                "tools": len(server_tools),
            }
        return {
            "total_tools": len(all_tools),
            "servers": servers,
            "cache": self._dispatcher._lru.stats(),
        }

    async def connect(
        self,
        server_name: str,
        base_url: str,
        pinned_tools: list[str] = [],
    ) -> None:
        """
        Auto-discover and register all tools from an MCP server.
        Stores the MCPConnection for lifecycle management.
        Pins specified tools in the LRU cache.
        """
        connection = await discover(server_name, base_url, self._registry)
        self._connections[server_name] = connection

        for tool_name in pinned_tools:
            tool_key = f"{server_name}::{tool_name}"
            self._dispatcher._lru.pin(tool_key)

    async def disconnect(self, server_name: str) -> None:
        """
        Close connection and mark server as DEAD.
        Silent if server_name not in _connections.
        """
        if server_name not in self._connections:
            return
        await self._connections[server_name].close()
        del self._connections[server_name]
        self._registry.update_health(server_name, HealthStatus.DEAD)

    async def disconnect_all(self) -> None:
        """Disconnect from every connected server."""
        for server_name in list(self._connections.keys()):
            await self.disconnect(server_name)
