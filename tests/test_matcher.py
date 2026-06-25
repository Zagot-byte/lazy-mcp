"""Tests for lazy_mcp.matcher — intent matching engine."""

import pytest
from unittest.mock import MagicMock

from lazy_mcp.matcher import Matcher
from lazy_mcp.models import ToolEntry, MatchType
from lazy_mcp.errors import NoMatchError


# ── Shared fixture ─────────────────────────────────────────────────────────────

@pytest.fixture
def tools():
    entry_search = ToolEntry(
        tool_key="brave::search",
        server_name="brave",
        tool_name="search",
        description="web search internet lookup find URLs current events browse",
        tags=["search", "web"],
        loader=MagicMock(),
    )
    entry_file = ToolEntry(
        tool_key="filesystem::read_file",
        server_name="filesystem",
        tool_name="read_file",
        description="read file open local disk storage get file contents",
        tags=["file", "read", "local"],
        loader=MagicMock(),
    )
    entry_email = ToolEntry(
        tool_key="gmail::send",
        server_name="gmail",
        tool_name="send",
        description="send email compose message mail recipient inbox",
        tags=["email", "send", "mail"],
        loader=MagicMock(),
    )
    return [entry_search, entry_file, entry_email]


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_exact_match(tools):
    matcher = Matcher()
    results = matcher.match("search", tools)
    assert results[0].tool_key == "brave::search"
    assert results[0].match_type == MatchType.EXACT
    assert results[0].confidence == 1.0


def test_keyword_match(tools):
    matcher = Matcher()
    results = matcher.match("search the web", tools)
    assert results[0].tool_key == "brave::search"
    assert results[0].match_type == MatchType.KEYWORD
    assert results[0].confidence > 0.0


def test_returns_sorted_by_confidence(tools):
    matcher = Matcher()
    results = matcher.match("web search", tools)
    confidences = [r.confidence for r in results]
    assert confidences == sorted(confidences, reverse=True)


def test_threshold_filters_low_confidence(tools):
    matcher = Matcher(threshold=0.9)
    # "read" only partially matches file tool — should be filtered at 0.9
    with pytest.raises(NoMatchError):
        matcher.match("read", tools)


def test_no_match_raises(tools):
    matcher = Matcher()
    with pytest.raises(NoMatchError):
        matcher.match("xkzqwerty gibberish", tools)


def test_semantic_hook_called_on_total_miss(tools):
    mock_hook = MagicMock(return_value=[])
    matcher = Matcher(semantic_hook=mock_hook)
    # semantic_hook returns [] which is falsy, but the hook returns directly
    # so an empty list is returned (no NoMatchError from hook path)
    # Actually per the code, if hook returns [], that's still empty results
    # and the code returns hook output directly — so we get []
    result = matcher.match("xkzqwerty gibberish", tools)
    mock_hook.assert_called_once()
    assert result == []


def test_semantic_hook_not_called_on_keyword_hit(tools):
    mock_hook = MagicMock()
    matcher = Matcher(semantic_hook=mock_hook)
    matcher.match("search the web", tools)
    mock_hook.assert_not_called()


def test_dedup_keeps_highest_confidence(tools):
    # a query that might match same tool via both exact and keyword
    matcher = Matcher()
    results = matcher.match("search", tools)
    tool_keys = [r.tool_key for r in results]
    # no duplicates
    assert len(tool_keys) == len(set(tool_keys))
