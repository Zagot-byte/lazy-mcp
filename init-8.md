SHARED CONTEXT (paste above)

Write lazy_mcp/__init__.py.

Export exactly these names and nothing else:
  from lazy_mcp.gateway import LazyMCP
  from lazy_mcp.errors import (ToolNotFoundError, ServerOfflineError, 
                                PartialResultError, DispatchError, NoMatchError)
  from lazy_mcp.models import DispatchResult, MatchResult, MatchType, HealthStatus

Set __version__ = "0.1.0"
Set __all__ as a list containing every exported name above.
