"""HTTP server exposing lazy-mcp's intent-based routing over the network.

Three endpoints:

* ``POST /tools/list`` — MCP-compatible tool listing with intentionally
  empty input schemas.  Clients see *what* tools exist but never get full
  schemas — that's the whole point.
* ``POST /ask``        — The core value: accept a natural-language intent,
  match it to the best tool, dispatch, and return the result.
* ``GET  /health``     — Lightweight status check.

The server owns its own :class:`ToolRegistry`, :class:`Matcher`, and
:class:`Dispatcher`.  It is **not** a wrapper around :class:`LazyMCP` —
it is a standalone process that speaks the same matching/dispatch logic
directly.
"""

import asyncio
import json
from typing import Any, Callable

from aiohttp import web

from lazy_mcp.registry import ToolRegistry
from lazy_mcp.matcher import Matcher
from lazy_mcp.dispatcher import Dispatcher
from lazy_mcp.models import DEFAULT_LRU_CAPACITY, DEFAULT_MATCH_THRESHOLD
from lazy_mcp.errors import (
    DispatchError,
    NoMatchError,
    ServerOfflineError,
    ToolNotFoundError,
)


class LazyMCPServer:
    """A standalone HTTP server that exposes lazy-mcp intent routing.

    Instantiates its own registry, matcher, and dispatcher.  Tools are
    registered via :meth:`register` before calling :meth:`start`.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        lru_capacity: int = DEFAULT_LRU_CAPACITY,
        match_threshold: float = DEFAULT_MATCH_THRESHOLD,
    ) -> None:
        self._registry: ToolRegistry = ToolRegistry()
        self._matcher: Matcher = Matcher(threshold=match_threshold)
        self._dispatcher: Dispatcher = Dispatcher(
            registry=self._registry, lru_capacity=lru_capacity,
        )

        self._app: web.Application = web.Application()
        self._app.router.add_post("/tools/list", self._handle_list)
        self._app.router.add_post("/ask", self._handle_ask)
        self._app.router.add_get("/capabilities", self._handle_capabilities)
        self._app.router.add_get("/health", self._handle_health)

        self._host: str = host
        self._port: int = port
        self._runner: web.AppRunner | None = None

    # ── tool registration ──────────────────────────────────────────────────

    def register(
        self,
        tool_name: str,
        description: str,
        handler: Callable,
        tags: list[str] = [],
        capabilities: list[str] = [],
        pinned: bool = False,
    ) -> str:
        """Register a tool under the implicit ``"local"`` server namespace.

        Returns the tool key ``"local::<tool_name>"``.
        If *pinned* is ``True``, the tool is pinned in the dispatcher LRU
        so it is never evicted.
        """
        tool_key = self._registry.register(
            server_name="local",
            tool_name=tool_name,
            description=description,
            loader=handler,
            tags=tags,
            capabilities=capabilities,
        )
        if pinned:
            self._dispatcher._lru.pin(tool_key)
        return tool_key

    # ── endpoint handlers ──────────────────────────────────────────────────

    async def _handle_list(self, request: web.Request) -> web.Response:
        """``POST /tools/list`` — MCP-compatible tool listing.

        Returns every registered tool with an intentionally empty
        ``inputSchema``.  MCP clients learn *what* exists but never
        receive full parameter schemas — callers should use ``/ask``
        with a natural-language intent instead.
        """
        tools = self._registry.all_tools()
        payload = {
            "tools": [
                {
                    "name": entry.tool_name,
                    "description": entry.description,
                    "inputSchema": {"type": "object", "properties": {}},
                }
                for entry in tools
            ],
        }
        return web.json_response(payload)

    async def _handle_capabilities(self, request: web.Request) -> web.Response:
        """
        GET /capabilities
        Returns: {"capabilities": self._registry.list_capabilities()}
        This is the ONLY discovery endpoint a lazy-mcp-aware LLM needs to call.
        """
        return web.json_response({"capabilities": self._registry.list_capabilities()})

    async def _handle_ask(self, request: web.Request) -> web.Response:
        """``POST /ask`` — capability-based dispatch (the core value).

        Expects a JSON body::

            {
                "capability": "file_access",
                "task": "read the file /tmp/hello.txt",
                "params": {"path": "/tmp/hello.txt"}
            }

        ``params`` is optional and defaults to ``{}``.
        """
        # ── 1. Parse body ──────────────────────────────────────────────────
        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                {"error": "invalid JSON body"}, status=400,
            )

        capability = body.get("capability")
        task = body.get("task")
        if not capability or not isinstance(capability, str):
            return web.json_response(
                {"error": "missing field: capability"}, status=400,
            )
        if not task or not isinstance(task, str):
            return web.json_response(
                {"error": "missing field: task"}, status=400,
            )

        params: dict[str, Any] = body.get("params", {})

        # ── 2. Match ──────────────────────────────────────────────────────
        tools = self._registry.all_tools()
        try:
            matches = self._matcher.match(capability, task, tools)
        except NoMatchError:
            return web.json_response({
                "success": False,
                "error": "no tool matched intent",
                "capability": capability,
                "task": task,
            })

        best = matches[0]  # highest confidence, already sorted

        # ── 3. Dispatch ───────────────────────────────────────────────────
        try:
            result = await self._dispatcher.dispatch(best.tool_key, params)
        except ServerOfflineError as e:
            return web.json_response(
                {"success": False, "error": f"server offline: {e}"},
                status=503,
            )
        except DispatchError as e:
            return web.json_response(
                {
                    "success": False,
                    "error": f"dispatch failed: {e.cause}",
                    "tool": e.tool_key,
                },
                status=500,
            )
        except Exception as e:
            return web.json_response(
                {"success": False, "error": str(e)},
                status=500,
            )

        return web.json_response({
            "success": True,
            "tool": best.tool_key,
            "confidence": best.confidence,
            "match_type": best.match_type.value,
            "result": result.result,
        })

    async def _handle_health(self, request: web.Request) -> web.Response:
        """``GET /health`` — lightweight server status."""
        tools = self._registry.all_tools()
        return web.json_response({
            "status": "ok",
            "total_tools": len(tools),
            "tools": [entry.tool_name for entry in tools],
            "cache": self._dispatcher._lru.stats(),
        })

    # ── server lifecycle ───────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the aiohttp server and run until cancelled."""
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()

        print(f"lazy-mcp server running on http://{self._host}:{self._port}")
        print(f"  /tools/list  — MCP compatible (minimal schemas)")
        print(f"  /ask         — lazy-mcp native (intent dispatch)")
        print(f"  /health      — server status")

        try:
            await asyncio.Event().wait()
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Cleanup the runner if running."""
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None


# ── convenience factory ────────────────────────────────────────────────────────

def serve(
    host: str = "0.0.0.0",
    port: int = 8000,
    lru_capacity: int = DEFAULT_LRU_CAPACITY,
    match_threshold: float = DEFAULT_MATCH_THRESHOLD,
) -> LazyMCPServer:
    """Create a configured :class:`LazyMCPServer` ready for tool registration.

    Returns the server instance so the caller can register tools before
    starting::

        server = serve(port=8000)
        server.register("search", "web search internet...", my_handler)
        asyncio.run(server.start())
    """
    return LazyMCPServer(
        host=host,
        port=port,
        lru_capacity=lru_capacity,
        match_threshold=match_threshold,
    )
