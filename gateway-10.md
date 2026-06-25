SHARED CONTEXT (paste above)

You already have lazy_mcp/gateway.py with class LazyMCP.
Add the following to it — do not rewrite the file, only add:

New import at top:
  from lazy_mcp.mcp_compat import MCPConnection, discover

New field on LazyMCP:
  _connections: dict[str, MCPConnection]    # server_name → live connection
  initialize it as {} in __init__

New method on LazyMCP:

  async def connect(self, server_name: str, base_url: str,
                    pinned_tools: list[str] = []) -> None:
    """
    Calls discover(server_name, base_url, self._registry).
    Stores the returned MCPConnection in self._connections[server_name].
    
    If pinned_tools is provided: for each tool_name in pinned_tools,
      build tool_key = f"{server_name}::{tool_name}"
      call self._dispatcher._lru.pin(tool_key)
    
    This is the primary user-facing onboarding method.
    Manual register() still exists for custom/static tools.
    """

  async def disconnect(self, server_name: str) -> None:
    """
    Call self._connections[server_name].close().
    Remove from self._connections.
    Call self._registry.update_health(server_name, HealthStatus.DEAD).
    Silent if server_name not in _connections.
    """

  async def disconnect_all(self) -> None:
    """
    Call disconnect() for every key in self._connections.
    Use list(self._connections.keys()) to avoid mutation during iteration.
    """