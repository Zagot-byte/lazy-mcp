SHARED CONTEXT — do not redefine these anywhere:

Python 3.11+. Type hints on everything. No third-party imports except where 
explicitly stated. Use dataclasses for data containers. Use OrderedDict for LRU.

NAMESPACE PATTERN: every tool is keyed as "server_name::tool_name" (two colons).
Example: "brave::search", "filesystem::read_file". This string is called tool_key.

CLASS NAMES (exact, do not rename):
  ToolEntry, ServerHealth, HealthStatus, DispatchResult, MatchResult, MatchType
  LRUCache, ToolRegistry, Dispatcher, LazyMCP

CONSTANTS (exact values):
  DEFAULT_LRU_CAPACITY = 32
  DEFAULT_MATCH_THRESHOLD = 0.3
  DEFAULT_HEALTH_FAIL_LIMIT = 3
  STREAM_TIMEOUT_SECONDS = 30

FILE LAYOUT:
  lazy_mcp/models.py
  lazy_mcp/errors.py
  lazy_mcp/lru.py
  lazy_mcp/matcher.py
  lazy_mcp/registry.py
  lazy_mcp/dispatcher.py
  lazy_mcp/gateway.py
  lazy_mcp/__init__.py
