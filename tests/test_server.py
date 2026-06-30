"""Tests for lazy_mcp.server — HTTP interface for LazyMCP."""

import pytest
import aiohttp
from lazy_mcp.server import LazyMCPServer


@pytest.fixture
async def server():
    # Spin up LazyMCPServer on a random port
    server = LazyMCPServer(host="127.0.0.1", port=0)
    server.register("search", "search the web", lambda params: {"results": []}, capabilities=["web_search"])
    server.register("read", "read file contents", lambda params: {"content": "ok"}, capabilities=["file_access"])
    
    # We setup the runner manually to bind to a random port
    server._runner = aiohttp.web.AppRunner(server._app)
    await server._runner.setup()
    site = aiohttp.web.TCPSite(server._runner, server._host, server._port)
    await site.start()
    
    port = site._server.sockets[0].getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    
    yield url
    
    await server.stop()


async def test_capabilities_endpoint(server):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{server}/capabilities") as resp:
            assert resp.status == 200
            data = await resp.json()
            assert "capabilities" in data
            assert data["capabilities"] == ["file_access", "web_search"]


async def test_ask_endpoint_success(server):
    async with aiohttp.ClientSession() as session:
        payload = {
            "capability": "web_search",
            "task": "search for python",
            "params": {"query": "python"}
        }
        async with session.post(f"{server}/ask", json=payload) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["success"] is True
            assert data["tool"] == "local::search"
            assert data["result"] == {"results": []}


async def test_ask_endpoint_missing_fields(server):
    async with aiohttp.ClientSession() as session:
        # missing task
        payload = {
            "capability": "web_search"
        }
        async with session.post(f"{server}/ask", json=payload) as resp:
            assert resp.status == 400
            data = await resp.json()
            assert "error" in data


async def test_ask_endpoint_no_match(server):
    async with aiohttp.ClientSession() as session:
        # nonexistent capability
        payload = {
            "capability": "code_execution",
            "task": "run print(1)"
        }
        async with session.post(f"{server}/ask", json=payload) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["success"] is False
            assert "error" in data
