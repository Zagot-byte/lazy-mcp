SHARED CONTEXT (paste above)

Write lazy_mcp/dispatcher.py.
Imports: asyncio, time, inspect, typing
         lazy_mcp.models (DispatchResult, HealthStatus)
         lazy_mcp.lru (LRUCache)
         lazy_mcp.registry (ToolRegistry)
         lazy_mcp.errors (ServerOfflineError, PartialResultError, DispatchError,
                          ToolNotFoundError)

Write one class: Dispatcher

Fields:
  _lru: LRUCache          # stores loader return values (full schema / connection)
  _registry: ToolRegistry

  __init__(self, registry: ToolRegistry, 
           lru_capacity: int = DEFAULT_LRU_CAPACITY)

Methods:

  async def dispatch(self, tool_key: str, params: dict) -> DispatchResult:
    """
    Main dispatch flow:

    1. Call _registry.get(tool_key) — raises ToolNotFoundError if missing,
       let it propagate.

    2. server_name = tool_key.split("::")[0]
       Check _registry.get_health(server_name).
       If status == DEAD: raise ServerOfflineError with server_name.

    3. Check _lru for tool_key. 
       Hit: use cached loader result (schema/connection already loaded).
       Miss: call _load_schema(tool_entry) to cold-load, store in _lru.

    4. Call _invoke(tool_entry, params) inside a try/except.
       On success: _registry.update_health(server_name, HealthStatus.WARM)
                   return DispatchResult(success=True, tool_key=tool_key,
                                        result=result, partial=False, 
                                        error_msg=None)
       On PartialResultError: 
                   _registry.update_health(server_name, HealthStatus.COLD,
                                           increment_fail=True)
                   return DispatchResult(success=False, tool_key=tool_key,
                                        result=e.partial_result, partial=True,
                                        error_msg=str(e))
       On any other Exception:
                   _registry.update_health(server_name, HealthStatus.COLD,
                                           increment_fail=True)
                   raise DispatchError(cause=e, tool_key=tool_key)
    """

  async def _load_schema(self, tool_entry) -> Any:
    """
    Call tool_entry.loader(). 
    If loader is a coroutine function (check with inspect.iscoroutinefunction):
      await it.
    Else: call it directly.
    Store result in _lru under tool_entry.tool_key.
    Return result.
    """

  async def _invoke(self, tool_entry, params: dict) -> Any:
    """
    Call the loaded schema/connection with params.
    Wrap in asyncio.wait_for with STREAM_TIMEOUT_SECONDS.
    On asyncio.TimeoutError: raise PartialResultError(partial_result=None,
      message=f"{tool_entry.tool_key} timed out after {STREAM_TIMEOUT_SECONDS}s")
    """
