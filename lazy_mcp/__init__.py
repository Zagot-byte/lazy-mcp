"""lazy_mcp — Lazy Model Context Protocol toolkit."""

from lazy_mcp.gateway import LazyMCP
from lazy_mcp.errors import (
    ToolNotFoundError,
    ServerOfflineError,
    PartialResultError,
    DispatchError,
    NoMatchError,
)
from lazy_mcp.models import DispatchResult, MatchResult, MatchType, HealthStatus
from lazy_mcp.server import LazyMCPServer, serve

__version__ = "0.1.0"

__all__ = [
    "LazyMCP",
    "ToolNotFoundError",
    "ServerOfflineError",
    "PartialResultError",
    "DispatchError",
    "NoMatchError",
    "DispatchResult",
    "MatchResult",
    "MatchType",
    "HealthStatus",
    "LazyMCPServer",
    "serve",
]
