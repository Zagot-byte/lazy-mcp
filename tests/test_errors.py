"""Tests for lazy_mcp.errors — exception hierarchy."""

import pytest

from lazy_mcp.errors import (
    DispatchError,
    LazyMCPError,
    NoMatchError,
    PartialResultError,
    ServerOfflineError,
    ToolNotFoundError,
)


# ── Hierarchy ──────────────────────────────────────────────────────────────────

def test_all_errors_inherit_from_base():
    for cls in (ToolNotFoundError, ServerOfflineError, PartialResultError,
                DispatchError, NoMatchError):
        assert issubclass(cls, LazyMCPError)
        assert issubclass(cls, Exception)


# ── ToolNotFoundError ──────────────────────────────────────────────────────────

def test_tool_not_found_basic():
    e = ToolNotFoundError("srv::missing")
    assert e.tool_key == "srv::missing"
    assert e.available_keys is None
    assert "srv::missing" in str(e)


def test_tool_not_found_suggests_close_match():
    e = ToolNotFoundError("srv::nope", available_keys=["srv::search", "other::x"])
    assert "srv::search" in str(e)
    assert "Did you mean" in str(e)


def test_tool_not_found_no_suggestion_when_no_overlap():
    e = ToolNotFoundError("a::b", available_keys=["x::y", "m::n"])
    assert "Did you mean" not in str(e)


# ── ServerOfflineError ─────────────────────────────────────────────────────────

def test_server_offline_basic():
    e = ServerOfflineError("brave")
    assert e.server_name == "brave"
    assert e.fail_count is None
    assert "brave" in str(e)
    assert "reset_health" in str(e)


def test_server_offline_with_fail_count():
    e = ServerOfflineError("fs", fail_count=5)
    assert "5 consecutive failures" in str(e)


# ── PartialResultError ─────────────────────────────────────────────────────────

def test_partial_result_with_data():
    e = PartialResultError(partial_result={"partial": True}, message="stream cut")
    assert e.partial_result == {"partial": True}
    assert "Partial data is attached" in str(e)


def test_partial_result_no_data():
    e = PartialResultError(partial_result=None, message="timeout")
    assert "No data recovered" in str(e)


def test_partial_result_with_tool_key():
    e = PartialResultError(
        partial_result=None, message="died", tool_key="srv::tool"
    )
    assert e.tool_key == "srv::tool"
    assert "[srv::tool]" in str(e)


# ── DispatchError ──────────────────────────────────────────────────────────────

def test_dispatch_error_wraps_cause():
    cause = ValueError("bad input")
    e = DispatchError(cause=cause, tool_key="s::t")
    assert e.cause is cause
    assert e.tool_key == "s::t"
    assert "ValueError" in str(e)
    assert "bad input" in str(e)


def test_dispatch_error_repr():
    e = DispatchError(cause=RuntimeError("boom"), tool_key="a::b")
    r = repr(e)
    assert "DispatchError" in r
    assert "a::b" in r


# ── NoMatchError ───────────────────────────────────────────────────────────────

def test_no_match_basic():
    e = NoMatchError("search the web")
    assert e.query == "search the web"
    assert e.threshold is None
    assert e.tool_count is None
    assert "search the web" in str(e)


def test_no_match_with_details():
    e = NoMatchError("search", threshold=0.3, tool_count=10)
    assert "threshold=0.30" in str(e)
    assert "searched 10 tool(s)" in str(e)


# ── repr ───────────────────────────────────────────────────────────────────────

def test_base_repr():
    e = LazyMCPError("test message")
    assert repr(e) == "LazyMCPError(test message)"
