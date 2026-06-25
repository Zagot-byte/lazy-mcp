SHARED CONTEXT (paste above)

Write lazy_mcp/models.py. No imports except dataclasses, enum, typing.

Define exactly these and nothing else:

HealthStatus(Enum): WARM, COLD, DEAD
  WARM = "warm"    # connected, recently used
  COLD = "cold"    # registered but untested
  DEAD = "dead"    # failed >= DEFAULT_HEALTH_FAIL_LIMIT times

ToolEntry(dataclass):
  tool_key: str          # "server::tool" — always derived, never set manually
  server_name: str
  tool_name: str
  description: str       # rich, keyword-dense, never shown to agent
  tags: list[str]        # additional match keywords, default empty list
  loader: Callable       # async or sync, returns dict of full schema — 
                         # never used for prompt injection, only for dispatcher

MatchType(Enum): EXACT, KEYWORD, SEMANTIC
  EXACT = "exact"        # query matched tool_name directly
  KEYWORD = "keyword"    # query matched description/tags by keyword overlap
  SEMANTIC = "semantic"  # reserved for ML fallback hook, not implemented yet

MatchResult(dataclass):
  tool_key: str
  confidence: float      # 0.0 to 1.0
  match_type: MatchType

DispatchResult(dataclass):
  success: bool
  tool_key: str
  result: Any            # the actual tool output
  partial: bool          # True if stream died mid-response
  error_msg: str | None  # None if success=True

ServerHealth(dataclass):
  server_name: str
  status: HealthStatus   # default COLD
  fail_count: int        # default 0
  last_checked: float    # unix timestamp, default 0.0
