"""Tests for lazy_mcp integration — full connect → ask flow with a fake MCP server."""

import json

import pytest
import aiohttp
import aiohttp.web

from lazy_mcp import LazyMCP
from lazy_mcp.models import HealthStatus


# ── Fake MCP server fixture ───────────────────────────────────────────────────

@pytest.fixture
async def mock_mcp_server():
    """Spin up a real HTTP server that speaks MCP JSON-RPC 2.0."""

    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        body = await request.json()
        method = body.get("method")
        req_id = body.get("id", 0)

        if method == "tools/list":
            return aiohttp.web.json_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "search",
                            "description": "web search internet lookup find URLs browse online",
                            "inputSchema": {
                                "properties": {"query": {"type": "string"}}
                            },
                            "capabilities": ["web_search"],
                        },
                        {
                            "name": "summarize",
                            "description": "summarize text content shorten document extract key points",
                            "inputSchema": {
                                "properties": {"text": {"type": "string"}}
                            },
                            "capabilities": ["summarize"],
                        },
                    ]
                },
            })
        elif method == "tools/call":
            tool_name = body["params"]["name"]
            return aiohttp.web.json_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": f"called {tool_name} successfully"}
                    ]
                },
            })
        else:
            return aiohttp.web.json_response(
                {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}},
                status=400,
            )

    app = aiohttp.web.Application()
    app.router.add_post("/", handler)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "localhost", 0)
    await site.start()

    # Get the actual bound port
    port = site._server.sockets[0].getsockname()[1]
    url = f"http://localhost:{port}"

    yield url

    await runner.cleanup()


# ── Tests ──────────────────────────────────────────────────────────────────────

async def test_connect_auto_registers_tools(mock_mcp_server):
    mcp = LazyMCP()
    await mcp.connect("testserver", mock_mcp_server)
    tools = mcp._registry.all_tools()
    tool_keys = [t.tool_key for t in tools]
    assert "testserver::search" in tool_keys
    assert "testserver::summarize" in tool_keys
    await mcp.disconnect_all()


async def test_ask_returns_result(mock_mcp_server):
    mcp = LazyMCP()
    await mcp.connect("testserver", mock_mcp_server)
    result = await mcp.ask("web_search", "search the web", {"query": "test"})
    assert result.success is True
    assert result.partial is False
    assert "search" in result.result[0]["text"]
    await mcp.disconnect_all()


async def test_ask_no_match_returns_failure(mock_mcp_server):
    mcp = LazyMCP()
    await mcp.connect("testserver", mock_mcp_server)
    result = await mcp.ask("nonexistent_capability", "xkzqwerty gibberish nonsense", {})
    assert result.success is False
    assert result.tool_key == ""
    await mcp.disconnect_all()


async def test_lru_warms_on_second_call(mock_mcp_server):
    mcp = LazyMCP()
    await mcp.connect("testserver", mock_mcp_server)
    await mcp.ask("web_search", "search the web", {"query": "first"})
    await mcp.ask("web_search", "search the web", {"query": "second"})
    stats = mcp.health()["cache"]
    assert stats["hits"] >= 1
    await mcp.disconnect_all()


async def test_server_marked_warm_after_success(mock_mcp_server):
    mcp = LazyMCP()
    await mcp.connect("testserver", mock_mcp_server)
    await mcp.ask("web_search", "search the web", {"query": "test"})
    health = mcp._registry.get_health("testserver")
    assert health.status == HealthStatus.WARM
    await mcp.disconnect_all()


async def test_available_returns_candidates_without_dispatch(mock_mcp_server):
    mcp = LazyMCP()
    await mcp.connect("testserver", mock_mcp_server)
    candidates = mcp.available("web_search", "search the web")
    assert len(candidates) > 0
    assert candidates[0].tool_key == "testserver::search"
    # verify no dispatch happened — health should still be COLD
    health = mcp._registry.get_health("testserver")
    assert health.status == HealthStatus.COLD
    await mcp.disconnect_all()


async def test_health_output_shape(mock_mcp_server):
    mcp = LazyMCP()
    await mcp.connect("testserver", mock_mcp_server)
    h = mcp.health()
    assert "total_tools" in h
    assert "servers" in h
    assert "testserver" in h["servers"]
    assert "cache" in h
    await mcp.disconnect_all()
