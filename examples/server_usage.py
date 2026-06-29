# run this, then in another terminal:
# curl -X POST http://localhost:8000/ask \
#   -H "Content-Type: application/json" \
#   -d '{"intent": "search for something", "params": {"query": "test"}}'
#
# curl http://localhost:8000/health

import asyncio
from datetime import datetime

from lazy_mcp import serve


server = serve(port=8000)


# ── tool handlers ──────────────────────────────────────────────────────────────

async def search_handler(params):
    return {"results": [f"result for: {params.get('query', '')}"]}


async def echo_handler(params):
    return params.get("message", "")


async def time_handler(params):
    return datetime.now().isoformat()


# ── registration ───────────────────────────────────────────────────────────────

server.register(
    tool_name="search",
    description="search web internet lookup find URLs browse online information",
    handler=search_handler,
    tags=["search", "web", "find"],
)

server.register(
    tool_name="echo",
    description="echo repeat back return input text string message",
    handler=echo_handler,
    tags=["echo", "repeat"],
)

server.register(
    tool_name="time",
    description="current time date now clock timestamp",
    handler=time_handler,
    tags=["time", "date", "clock"],
)

print("registered tools:", [t.tool_key for t in server._registry.all_tools()])

asyncio.run(server.start())
