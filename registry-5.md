SHARED CONTEXT (paste above)

Write lazy_mcp/registry.py.
Imports: time, typing, lazy_mcp.models (ToolEntry, ServerHealth, HealthStatus)
         lazy_mcp.errors (ToolNotFoundError)

Write one class: ToolRegistry

Fields (private):
  _index: dict[str, ToolEntry]          # tool_key → ToolEntry
  _health: dict[str, ServerHealth]      # server_name → ServerHealth

Methods:

  register(self, server_name: str, tool_name: str, description: str, 
           loader: Callable, tags: list[str] = []) -> str:
    """
    Builds tool_key = f"{server_name}::{tool_name}".
    Creates ToolEntry, stores in _index under tool_key.
    If server_name not in _health, create ServerHealth(server_name, 
      status=HealthStatus.COLD, fail_count=0, last_checked=0.0).
    Returns tool_key.
    Silent overwrite if tool_key already exists (namespace prevents collisions,
    re-registration means schema update).
    """

  get(self, tool_key: str) -> ToolEntry:
    """Raises ToolNotFoundError if not found."""

  all_tools(self) -> list[ToolEntry]:
    """Return list of all registered ToolEntry values."""

  tools_for_server(self, server_name: str) -> list[ToolEntry]:
    """Return all tools whose server_name matches."""

  update_health(self, server_name: str, status: HealthStatus, 
                increment_fail: bool = False) -> None:
    """
    Update ServerHealth for server_name.
    If increment_fail=True: fail_count += 1.
    If fail_count >= DEFAULT_HEALTH_FAIL_LIMIT: force status = DEAD.
    Set last_checked = time.time().
    Silent if server_name not in _health (means no tools registered for it).
    """

  get_health(self, server_name: str) -> ServerHealth | None:
    """Return ServerHealth or None if server not registered."""

  reset_health(self, server_name: str) -> None:
    """Set status=COLD, fail_count=0. Used after manual reconnect."""
