"""Tool registry and server health tracking for lazy_mcp."""

import time
from typing import Callable

from lazy_mcp.models import (
    DEFAULT_HEALTH_FAIL_LIMIT,
    HealthStatus,
    ServerHealth,
    ToolEntry,
)
from lazy_mcp.errors import ToolNotFoundError


class ToolRegistry:
    """Stores registered tools and tracks server health."""

    def __init__(self) -> None:
        self._index: dict[str, ToolEntry] = {}
        self._health: dict[str, ServerHealth] = {}

    def register(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        loader: Callable,
        tags: list[str] = [],
        capabilities: list[str] = [],
    ) -> str:
        """
        Register a tool. Builds tool_key = "server_name::tool_name".
        Silent overwrite if tool_key already exists.
        Returns tool_key.
        """
        tool_key = f"{server_name}::{tool_name}"
        self._index[tool_key] = ToolEntry(
            tool_key=tool_key,
            server_name=server_name,
            tool_name=tool_name,
            description=description,
            loader=loader,
            tags=tags,
            capabilities=capabilities,
        )
        if server_name not in self._health:
            self._health[server_name] = ServerHealth(
                server_name=server_name,
                status=HealthStatus.COLD,
                fail_count=0,
                last_checked=0.0,
            )
        return tool_key

    def get(self, tool_key: str) -> ToolEntry:
        """Raises ToolNotFoundError if not found."""
        if tool_key not in self._index:
            raise ToolNotFoundError(
                tool_key, available_keys=list(self._index.keys())
            )
        return self._index[tool_key]

    def all_tools(self) -> list[ToolEntry]:
        """Return list of all registered ToolEntry values."""
        return list(self._index.values())

    def tools_for_server(self, server_name: str) -> list[ToolEntry]:
        """Return all tools whose server_name matches."""
        return [t for t in self._index.values() if t.server_name == server_name]

    def list_capabilities(self) -> list[str]:
        """
        Return the sorted, deduplicated list of all capability labels 
        across every registered tool. This is the vocabulary sent to the LLM —
        cheap, flat, no schemas.
        
        Example output: ["code_execution", "file_access", "web_search"]
        """
        caps = set()
        for tool in self._index.values():
            caps.update(tool.capabilities)
        return sorted(list(caps))

    def update_health(
        self,
        server_name: str,
        status: HealthStatus,
        increment_fail: bool = False,
    ) -> None:
        """
        Update ServerHealth for server_name.
        If increment_fail=True: fail_count += 1.
        If fail_count >= DEFAULT_HEALTH_FAIL_LIMIT: force status = DEAD.
        Silent if server_name not in _health.
        """
        if server_name not in self._health:
            return
        health = self._health[server_name]
        health.status = status
        if increment_fail:
            health.fail_count += 1
        if health.fail_count >= DEFAULT_HEALTH_FAIL_LIMIT:
            health.status = HealthStatus.DEAD
        health.last_checked = time.time()

    def get_health(self, server_name: str) -> ServerHealth | None:
        """Return ServerHealth or None if server not registered."""
        return self._health.get(server_name)

    def reset_health(self, server_name: str) -> None:
        """Set status=COLD, fail_count=0. Used after manual reconnect."""
        if server_name in self._health:
            self._health[server_name].status = HealthStatus.COLD
            self._health[server_name].fail_count = 0
