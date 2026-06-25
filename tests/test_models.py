"""Tests for lazy_mcp.models — enums and dataclasses."""

from lazy_mcp.models import (
    DEFAULT_HEALTH_FAIL_LIMIT,
    DEFAULT_LRU_CAPACITY,
    DEFAULT_MATCH_THRESHOLD,
    STREAM_TIMEOUT_SECONDS,
    DispatchResult,
    HealthStatus,
    MatchResult,
    MatchType,
    ServerHealth,
    ToolEntry,
)


# ── Constants ──────────────────────────────────────────────────────────────────

def test_constants_have_expected_values():
    assert DEFAULT_LRU_CAPACITY == 32
    assert DEFAULT_MATCH_THRESHOLD == 0.3
    assert DEFAULT_HEALTH_FAIL_LIMIT == 3
    assert STREAM_TIMEOUT_SECONDS == 30


# ── HealthStatus ───────────────────────────────────────────────────────────────

def test_health_status_values():
    assert HealthStatus.WARM.value == "warm"
    assert HealthStatus.COLD.value == "cold"
    assert HealthStatus.DEAD.value == "dead"


def test_health_status_is_enum():
    assert len(HealthStatus) == 3


# ── MatchType ──────────────────────────────────────────────────────────────────

def test_match_type_values():
    assert MatchType.EXACT.value == "exact"
    assert MatchType.KEYWORD.value == "keyword"
    assert MatchType.SEMANTIC.value == "semantic"


# ── ToolEntry ──────────────────────────────────────────────────────────────────

def test_tool_entry_defaults():
    entry = ToolEntry(
        tool_key="srv::t",
        server_name="srv",
        tool_name="t",
        description="desc",
    )
    assert entry.tags == []
    assert entry.loader is not None  # default lambda


def test_tool_entry_with_tags():
    entry = ToolEntry(
        tool_key="a::b",
        server_name="a",
        tool_name="b",
        description="d",
        tags=["x", "y"],
        loader=lambda: "schema",
    )
    assert entry.tags == ["x", "y"]
    assert entry.loader() == "schema"


# ── MatchResult ────────────────────────────────────────────────────────────────

def test_match_result_fields():
    m = MatchResult(tool_key="s::t", confidence=0.85, match_type=MatchType.KEYWORD)
    assert m.tool_key == "s::t"
    assert m.confidence == 0.85
    assert m.match_type == MatchType.KEYWORD


# ── DispatchResult ─────────────────────────────────────────────────────────────

def test_dispatch_result_success():
    r = DispatchResult(
        success=True, tool_key="s::t", result={"data": 1},
        partial=False, error_msg=None,
    )
    assert r.success is True
    assert r.error_msg is None


def test_dispatch_result_failure():
    r = DispatchResult(
        success=False, tool_key="s::t", result=None,
        partial=True, error_msg="stream died",
    )
    assert r.success is False
    assert r.partial is True
    assert r.error_msg == "stream died"


# ── ServerHealth ───────────────────────────────────────────────────────────────

def test_server_health_defaults():
    h = ServerHealth(server_name="test")
    assert h.status == HealthStatus.COLD
    assert h.fail_count == 0
    assert h.last_checked == 0.0
