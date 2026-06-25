SHARED CONTEXT (paste above)

Write lazy_mcp/matcher.py.
Imports: re, typing, lazy_mcp.models (ToolEntry, MatchResult, MatchType)
         lazy_mcp.errors (NoMatchError)

Write one class: Matcher

Fields:
  _threshold: float      # default DEFAULT_MATCH_THRESHOLD
  _semantic_hook: Callable[[str, list[ToolEntry]], list[MatchResult]] | None
                         # default None — slot for future ML, never call if None

Methods:

  __init__(self, threshold: float = DEFAULT_MATCH_THRESHOLD, 
           semantic_hook=None)

  match(self, query: str, tools: list[ToolEntry]) -> list[MatchResult]:
    """
    Returns list of MatchResult sorted by confidence descending.
    Raises NoMatchError if nothing clears threshold after all strategies.
    
    Strategy order:
    1. EXACT: normalize query and tool_name (lowercase, strip), check equality.
       confidence = 1.0 on exact match.
    2. KEYWORD: tokenize query by whitespace+punctuation into lowercase tokens.
       For each ToolEntry, count how many query tokens appear in 
       (description.lower() + " " + " ".join(tags).lower()).
       confidence = matched_token_count / total_query_token_count.
       Include if confidence >= _threshold.
    3. SEMANTIC: only if _semantic_hook is not None AND step 1+2 produced 
       no results. Call _semantic_hook(query, tools), return its output directly.
    
    Dedup by tool_key — keep highest confidence if same key appears from 
    multiple strategies.
    """

  _tokenize(self, text: str) -> list[str]:
    """Split on whitespace and punctuation, lowercase, remove empty strings."""
    # use re.split(r'[\s\W]+', text.lower())
