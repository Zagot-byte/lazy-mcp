"""MCP protocol compatibility layer for lazy_mcp."""

import asyncio
import json
import time
from typing import Any, Callable

import aiohttp

from lazy_mcp.models import HealthStatus, ServerHealth, ToolEntry
from lazy_mcp.errors import PartialResultError, ServerOfflineError


class MCPConnection:
    """JSON-RPC 2.0 client for communicating with MCP servers."""

    def __init__(self, server_name: str, base_url: str) -> None:
        self.server_name: str = server_name
        self.base_url: str = base_url
        self._session: aiohttp.ClientSession | None = None
        self._request_counter: int = 0

    async def connect(self) -> None:
        """Open aiohttp.ClientSession. Raise ServerOfflineError if connection cannot be established."""
        try:
            self._session = aiohttp.ClientSession()
        except Exception as e:
            raise ServerOfflineError(self.server_name)

    async def close(self) -> None:
        """Close _session if open. Set to None."""
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def list_tools(self) -> list[dict]:
        """
        POST to base_url with method "tools/list", params={}.
        Return the list at response["result"]["tools"].
        Raise ServerOfflineError on HTTP error or timeout.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {},
        }
        try:
            async with self._session.post(self.base_url, json=payload) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data["result"]["tools"]
        except Exception as e:
            raise ServerOfflineError(self.server_name) from e

    async def call_tool(self, tool_name: str, params: dict) -> Any:
        """
        POST to base_url with method "tools/call".
        Return response["result"]["content"] directly.
        Raise ServerOfflineError on HTTP error or timeout.
        Raise PartialResultError if response has no "result" key.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": params},
        }
        try:
            async with self._session.post(self.base_url, json=payload) as resp:
                resp.raise_for_status()
                data = await resp.json()
                if "result" not in data:
                    raise PartialResultError(
                        partial_result=data,
                        message="No 'result' key in response",
                        tool_key=f"{self.server_name}::{tool_name}",
                    )
                return data["result"]["content"]
        except PartialResultError:
            raise
        except Exception as e:
            raise ServerOfflineError(self.server_name) from e

    def make_loader(self, tool_name: str) -> Callable:
        """
        Return an async closure that calls self.call_tool(tool_name, params).
        This is what gets stored as ToolEntry.loader at registration time.
        """
        async def loader(params: dict = {}) -> Any:
            return await self.call_tool(tool_name, params)
        return loader

    def _next_id(self) -> int:
        """Increment _request_counter and return it."""
        self._request_counter += 1
        return self._request_counter


async def discover(
    server_name: str,
    base_url: str,
    registry: Any,
) -> MCPConnection:
    """
    Full auto-registration flow:
    1. Create MCPConnection.
    2. Connect to server.
    3. List tools.
    4. Register each tool in the registry.
    5. Return the MCPConnection for lifecycle management.

    registry parameter is typed as Any to avoid circular import —
    the actual type is ToolRegistry.
    """
    connection = MCPConnection(server_name, base_url)
    await connection.connect()
    tools = await connection.list_tools()
    for tool in tools:
        loader = connection.make_loader(tool["name"])
        tags = list(
            tool.get("inputSchema", {}).get("properties", {}).keys()
        )
        registry.register(
            server_name=server_name,
            tool_name=tool["name"],
            description=tool["description"],
            loader=loader,
            tags=tags,
        )
    return connection
