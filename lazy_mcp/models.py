"""Data models for lazy_mcp — enums and dataclasses."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


# ── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_LRU_CAPACITY: int = 32
DEFAULT_MATCH_THRESHOLD: float = 0.3
DEFAULT_HEALTH_FAIL_LIMIT: int = 3
STREAM_TIMEOUT_SECONDS: int = 30


# ── Enums ──────────────────────────────────────────────────────────────────────

class HealthStatus(Enum):
    """Health state of an MCP server."""
    WARM = "warm"    # connected, recently used
    COLD = "cold"    # registered but untested
    DEAD = "dead"    # failed >= DEFAULT_HEALTH_FAIL_LIMIT times


class MatchType(Enum):
    """How a tool was matched to a query."""
    EXACT = "exact"        # query matched tool_name directly
    KEYWORD = "keyword"    # query matched description/tags by keyword overlap
    SEMANTIC = "semantic"  # reserved for ML fallback hook, not implemented yet


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class ToolEntry:
    """A registered tool with its metadata and lazy loader."""
    tool_key: str          # "server::tool" — always derived, never set manually
    server_name: str
    tool_name: str
    description: str       # rich, keyword-dense, never shown to agent
    tags: list[str] = field(default_factory=list)  # additional match keywords
    capabilities: list[str] = field(default_factory=list)  # closed-vocabulary labels, e.g. ["file_access"]
    loader: Callable = field(default=lambda: None)  # async or sync, returns dict of full schema


@dataclass
class MatchResult:
    """Result of matching a query to a tool."""
    tool_key: str
    confidence: float      # 0.0 to 1.0
    match_type: MatchType


@dataclass
class DispatchResult:
    """Result of dispatching a tool call."""
    success: bool
    tool_key: str
    result: Any            # the actual tool output
    partial: bool          # True if stream died mid-response
    error_msg: str | None  # None if success=True


@dataclass
class ServerHealth:
    """Health tracking for a server."""
    server_name: str
    status: HealthStatus = HealthStatus.COLD   # default COLD
    fail_count: int = 0                        # default 0
    last_checked: float = 0.0                  # unix timestamp, default 0.0
