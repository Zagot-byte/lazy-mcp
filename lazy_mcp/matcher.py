"""Tool matching engine for lazy_mcp using capability filtering and BM25 ranking."""

import re
from typing import Callable
from rank_bm25 import BM25Okapi

from lazy_mcp.models import ToolEntry, MatchResult, MatchType, DEFAULT_MATCH_THRESHOLD
from lazy_mcp.errors import NoMatchError


STOPWORDS = {"the", "a", "an", "for", "in", "to", "of", "and", "or", 
             "is", "it", "with", "on", "at"}


class Matcher:
    """Matches capabilities and natural-language tasks to registered tools."""

    def __init__(
        self,
        threshold: float = DEFAULT_MATCH_THRESHOLD,
        semantic_hook: Callable | None = None,
    ) -> None:
        self._threshold: float = threshold
        self._semantic_hook: Callable | None = semantic_hook

    def _tokenize(self, text: str) -> list[str]:
        r"""
        re.split(r'[\s\W]+', text.lower()), drop empty strings and STOPWORDS.
        """
        tokens = re.split(r"[\s\W]+", text.lower())
        return [t for t in tokens if t and t not in STOPWORDS]

    def match(
        self,
        capability: str,
        task: str,
        tools: list[ToolEntry],
    ) -> list[MatchResult]:
        """
        Two-stage match:

        STAGE 1 — capability filter (exact, required):
          candidates = [t for t in tools if capability in t.capabilities]
          If candidates is empty: raise NoMatchError 
            (f"no tool registered for capability '{capability}'")

        STAGE 2 — BM25 rank candidates by task text:
          If only one candidate: return it directly with 
            MatchResult(tool_key, confidence=1.0, match_type=MatchType.EXACT)
            (no need to rank a field of one)

          If multiple candidates:
            corpus = [self._tokenize(t.description + " " + " ".join(t.tags)) 
                       for t in candidates]
            bm25 = BM25Okapi(corpus)
            query_tokens = self._tokenize(task)
            
            # Check if query_tokens is empty
            if not query_tokens:
                raise NoMatchError("task too vague to disambiguate")

            scores = bm25.get_scores(query_tokens)
            
            Normalize scores to 0-1 range: 
              max_score = max(scores) if scores else 1.0
              normalized = [s / max_score if max_score > 0 else 0.0 for s in scores]
            
            results = [
              MatchResult(tool_key=candidates[i].tool_key, 
                          confidence=normalized[i],
                          match_type=MatchType.KEYWORD)
              for i in range(len(candidates))
            ]
            results.sort(key=lambda r: r.confidence, reverse=True)
            
            Filter by threshold. If empty after filtering and _semantic_hook 
            is not None: call _semantic_hook(task, candidates), return its output.
            If still empty: raise NoMatchError(f"no tool matched task within 
              capability '{capability}'")
            
            Dedup by tool_key, keep highest confidence.
            Return sorted results.
        """
        # STAGE 1 — capability filter (exact, required)
        candidates = [t for t in tools if capability in t.capabilities]
        if not candidates:
            raise NoMatchError(f"no tool registered for capability '{capability}'")

        # STAGE 2 — BM25 rank candidates by task text
        if len(candidates) == 1:
            return [
                MatchResult(
                    tool_key=candidates[0].tool_key,
                    confidence=1.0,
                    match_type=MatchType.EXACT,
                )
            ]

        query_tokens = self._tokenize(task)
        if not query_tokens:
            raise NoMatchError("task too vague to disambiguate")

        corpus = [
            self._tokenize(t.description + " " + " ".join(t.tags))
            for t in candidates
        ]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(query_tokens)

        # Normalize scores to 0-1 range
        max_score = max(scores) if len(scores) > 0 else 0.0
        if max_score <= 0.0:
            # Fallback to term overlap count for small corpora where BM25 IDF is 0/negative
            scores = []
            for doc in corpus:
                doc_set = set(doc)
                scores.append(sum(1 for token in query_tokens if token in doc_set))
            max_score = max(scores) if len(scores) > 0 else 0.0

        normalized = [
            s / max_score if max_score > 0 else 0.0
            for s in scores
        ]

        results = [
            MatchResult(
                tool_key=candidates[i].tool_key,
                confidence=normalized[i],
                match_type=MatchType.KEYWORD,
            )
            for i in range(len(candidates))
        ]

        # Sort by confidence descending
        results.sort(key=lambda r: r.confidence, reverse=True)

        # Filter by threshold
        filtered_results = [r for r in results if r.confidence >= self._threshold]

        if not filtered_results:
            if self._semantic_hook is not None:
                return self._semantic_hook(task, candidates)
            raise NoMatchError(
                f"no tool matched task within capability '{capability}'"
            )

        # Dedup by tool_key, keep highest confidence.
        # Since they are sorted by confidence descending, the first occurrence is the highest.
        seen_keys = set()
        deduped_results = []
        for r in filtered_results:
            if r.tool_key not in seen_keys:
                seen_keys.add(r.tool_key)
                deduped_results.append(r)

        return deduped_results
