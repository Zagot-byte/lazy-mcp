SHARED CONTEXT (paste above)

Write lazy_mcp/gateway.py.
Imports: typing
         lazy_mcp.models (DispatchResult, MatchResult)
         lazy_mcp.registry (ToolRegistry)
         lazy_mcp.matcher (Matcher)
         lazy_mcp.dispatcher (Dispatcher)
         lazy_mcp.errors (NoMatchError, ToolNotFoundError, ServerOfflineError,
                          DispatchError)

Write one class: LazyMCP
This is the ONLY class an external caller ever touches. 
All other classes are internal implementation.

Fields:
  _registry: ToolRegistry
  _matcher: Matcher
  _dispatcher: Dispatcher

  __init__(self, lru_capacity: int = DEFAULT_LRU_CAPACITY,
           match_threshold: float = DEFAULT_MATCH_THRESHOLD,
           semantic_hook=None)
    — instantiate all three internals here

Methods:

  def register(self, server_name: str, tool_name: str, 
               description: str, loader: Callable,
               tags: list[str] = [], pinned: bool = False) -> str:
    """
    Delegates to _registry.register(...).
    If pinned=True: call _dispatcher._lru.pin(tool_key).
    Returns tool_key.
    """

  async def ask(self, intent: str, params: dict = {}) -> DispatchResult:
    """
    This is the main entry point. Agent calls this with plain intent.
    Agent never sees a schema.

    Flow:
    1. tools = _registry.all_tools()
    2. matches = _matcher.match(intent, tools)
       On NoMatchError: return DispatchResult(success=False, tool_key="",
                         result=None, partial=False, 
                         error_msg="No tool available for this intent")
    3. best = matches[0]  (highest confidence, already sorted)
    4. result = await _dispatcher.dispatch(best.tool_key, params)
    5. return result
    """

  def available(self, intent: str) -> list[MatchResult]:
    """
    Dry-run match — returns candidates without dispatching.
    Agent can call this to check before committing.
    Returns [] on NoMatchError (don't raise here).
    """

  def health(self) -> dict:
    """
    Return a summary dict:
    {
      "total_tools": int,
      "servers": {
        server_name: {"status": str, "fail_count": int, "tools": int}
      },
      "cache": _dispatcher._lru.stats()
    }
    """
