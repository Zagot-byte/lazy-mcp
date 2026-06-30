"""Tests for lazy_mcp.matcher — capability-based and BM25 intent matching engine."""

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
        capabilities=["web_search", "lookup"],
        loader=MagicMock(),
    )
    entry_file = ToolEntry(
        tool_key="filesystem::read_file",
        server_name="filesystem",
        tool_name="read_file",
        description="read file open local disk storage get file contents",
        tags=["file", "read", "local"],
        capabilities=["file_access", "lookup"],
        loader=MagicMock(),
    )
    entry_email = ToolEntry(
        tool_key="gmail::send",
        server_name="gmail",
        tool_name="send",
        description="send email compose message mail recipient inbox",
        tags=["email", "send", "mail"],
        capabilities=["email_compose"],
        loader=MagicMock(),
    )
    return [entry_search, entry_file, entry_email]


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_capability_filter_no_match(tools):
    matcher = Matcher()
    # capability not registered
    with pytest.raises(NoMatchError, match="no tool registered for capability 'database_query'"):
        matcher.match("database_query", "find users", tools)


def test_single_candidate_short_circuits(tools):
    matcher = Matcher()
    # "email_compose" only has one tool, gmail::send
    results = matcher.match("email_compose", "anything here", tools)
    assert len(results) == 1
    assert results[0].tool_key == "gmail::send"
    assert results[0].match_type == MatchType.EXACT
    assert results[0].confidence == 1.0


def test_multiple_candidates_ranked_by_bm25(tools):
    matcher = Matcher()
    # "lookup" is on brave::search and filesystem::read_file
    # task query mentions "web internet" -> should match brave::search better
    results = matcher.match("lookup", "web search internet", tools)
    assert results[0].tool_key == "brave::search"
    assert results[0].match_type == MatchType.KEYWORD
    assert results[0].confidence == 1.0  # max score gets normalized to 1.0

    # task query mentions "local disk file" -> should match filesystem::read_file better
    results2 = matcher.match("lookup", "local disk file contents", tools)
    assert results2[0].tool_key == "filesystem::read_file"
    assert results2[0].match_type == MatchType.KEYWORD
    assert results2[0].confidence == 1.0


def test_threshold_filters_low_confidence(tools):
    matcher = Matcher(threshold=0.9)
    # Completely unrelated query -> scores are all 0 -> confidence 0 -> filtered by threshold
    with pytest.raises(NoMatchError, match="no tool matched task within capability 'lookup'"):
        matcher.match("lookup", "completely unrelated words", tools)


def test_empty_query_tokens_raises(tools):
    matcher = Matcher()
    # task is empty
    with pytest.raises(NoMatchError, match="task too vague to disambiguate"):
        matcher.match("lookup", "", tools)
    
    # task is pure stopwords
    with pytest.raises(NoMatchError, match="task too vague to disambiguate"):
        matcher.match("lookup", "the and for in", tools)


def test_semantic_hook_called_on_total_miss(tools):
    mock_hook = MagicMock(return_value=[])
    matcher = Matcher(threshold=0.9, semantic_hook=mock_hook)
    
    # query completely unrelated -> filters to empty list -> semantic hook is called
    result = matcher.match("lookup", "completely unrelated words", tools)
    mock_hook.assert_called_once()
    assert result == []


def test_semantic_hook_not_called_on_hit(tools):
    mock_hook = MagicMock()
    matcher = Matcher(semantic_hook=mock_hook)
    
    matcher.match("lookup", "web search", tools)
    mock_hook.assert_not_called()
