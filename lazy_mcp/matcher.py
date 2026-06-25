"""Tool matching engine for lazy_mcp."""

import re
from typing import Callable

from lazy_mcp.models import (
    DEFAULT_MATCH_THRESHOLD,
    MatchResult,
    MatchType,
    ToolEntry,
)
from lazy_mcp.errors import NoMatchError


class Matcher:
    """Matches natural-language queries to registered tools."""

    def __init__(
        self,
        threshold: float = DEFAULT_MATCH_THRESHOLD,
        semantic_hook: Callable | None = None,
    ) -> None:
        self._threshold: float = threshold
        self._semantic_hook: Callable | None = semantic_hook

    def match(self, query: str, tools: list[ToolEntry]) -> list[MatchResult]:
        """
        Returns list of MatchResult sorted by confidence descending.
        Raises NoMatchError if nothing clears threshold after all strategies.

        Strategy order:
        1. EXACT — normalized query == tool_name
        2. KEYWORD — token overlap against description + tags
        3. SEMANTIC — fallback hook if provided and no results from 1+2
        """
        results: dict[str, MatchResult] = {}

        # Strategy 1: EXACT match
        normalized_query = query.lower().strip()
        for tool in tools:
            if normalized_query == tool.tool_name.lower().strip():
                results[tool.tool_key] = MatchResult(
                    tool_key=tool.tool_key,
                    confidence=1.0,
                    match_type=MatchType.EXACT,
                )

        # Strategy 2: KEYWORD match
        query_tokens = self._tokenize(query)
        if query_tokens:
            for tool in tools:
                corpus = tool.description.lower() + " " + " ".join(tool.tags).lower()
                matched_count = sum(
                    1 for token in query_tokens if token in corpus
                )
                confidence = matched_count / len(query_tokens)
                if confidence >= self._threshold:
                    # Keep highest confidence per tool_key (dedup)
                    if tool.tool_key not in results or confidence > results[tool.tool_key].confidence:
                        results[tool.tool_key] = MatchResult(
                            tool_key=tool.tool_key,
                            confidence=confidence,
                            match_type=MatchType.KEYWORD,
                        )

        # Strategy 3: SEMANTIC fallback
        if not results and self._semantic_hook is not None:
            return self._semantic_hook(query, tools)

        if not results:
            raise NoMatchError(
                query=query,
                threshold=self._threshold,
                tool_count=len(tools),
            )

        # Sort by confidence descending
        return sorted(results.values(), key=lambda r: r.confidence, reverse=True)

    def _tokenize(self, text: str) -> list[str]:
        """Split on whitespace and punctuation, lowercase, remove empty strings."""
        return [t for t in re.split(r"[\s\W]+", text.lower()) if t]
