# lazy-mcp

Tool-dispatch middleware for LLM agents. Keeps tool schemas out of your prompt entirely.

---

## The problem

When an LLM agent has many registered tools, the standard approach dumps every tool's full schema into the system prompt on every call:

```
[tool: brave_search]
description: Search the web for current information...
parameters:
  query (string, required): The search query
  count (integer): Number of results, default 10
  ...
```

Multiply that by every tool you have registered. At 150–400 tokens per schema, it adds up fast — and most of those tokens describe tools that won't be used in this call at all.

### The actual token math

| Setup | Tools | Tokens per schema | Wasted tokens per call |
|---|---|---|---|
| Small agent | 5 | 150 | 600 (4 unused tools) |
| Medium agent | 15 | 250 | 3,500 (14 unused) |
| Large agent | 40 | 400 | 15,600 (39 unused) |

At GPT-4 pricing (~$0.01/1K tokens), a large agent running 1,000 calls/day wastes **~$156/day** on schema tokens alone. On a local model with a 4K context window, 15 tools can consume 60% of your context before the actual task even starts.

### What lazy-mcp does

The agent never sees a schema. It fires a plain intent:

```
"search the web for X"
```

lazy-mcp intercepts, resolves the right tool, dispatches the call, and returns only the result. Schema cost to the agent: zero, always.

---

## How it works

```
Agent
  │  intent: "search the web for X"   ← no schema in context, ever
  ▼
lazy-mcp
  ├── match intent against rich descriptions (private, agent never sees these)
  ├── health check → is this server alive?
  ├── LRU check → is this tool warm?
  └── dispatch → MCP server → result
  │
  ▼
Agent
  │  result only
```

Three internal structures:

- **Hashmap** — `tool_key → ToolEntry` with a rich, keyword-dense description. O(1) lookup. Agent never sees this.
- **LRU cache** — tracks warm servers and recently used tool connections. Avoids cold-loading on repeat calls.
- **Matcher** — keyword overlap against descriptions. Finds the right tool from a plain intent string, no schema needed.

Tool keys are namespaced: `server_name::tool_name`. `brave::search`, `filesystem::read_file`. Collision-proof across servers.

---

## Install

```bash
pip install lazy-mcp
```

Or from source:

```bash
git clone https://github.com/your-handle/lazy-mcp
cd lazy-mcp
pip install -e .
```

**Requires:** Python 3.11+, `aiohttp`

---

## Quickstart

### With a real MCP server

```python
import asyncio
from lazy_mcp import LazyMCP

async def main():
    mcp = LazyMCP()

    # connect() calls tools/list on the server and auto-registers everything
    await mcp.connect("brave", "http://localhost:3000")
    await mcp.connect("filesystem", "http://localhost:3001")

    # agent fires plain intent — no schema, no tool names
    result = await mcp.ask(
        "search the web",
        {"query": "lazy evaluation in Python"}
    )

    print(result.result)

    await mcp.disconnect_all()

asyncio.run(main())
```

### With manual registration (no MCP server needed)

```python
from lazy_mcp import LazyMCP

async def fake_search_loader(params: dict):
    return {"results": [f"result for: {params.get('query')}"]}

mcp = LazyMCP()

mcp.register(
    server_name="brave",
    tool_name="search",
    description="web search internet lookup find URLs current events browse online",
    loader=fake_search_loader,
    tags=["search", "web", "fetch"]
)

# check what's available without dispatching
candidates = mcp.available("search the internet")
# → [MatchResult(tool_key="brave::search", confidence=0.8, match_type=KEYWORD)]

result = await mcp.ask("search the internet", {"query": "test"})
print(result.success)   # True
print(result.result)    # {"results": ["result for: test"]}
```

---

## API

### `LazyMCP`

The only class you need. Everything else is internal.

```python
LazyMCP(
    lru_capacity: int = 32,
    match_threshold: float = 0.3,
    semantic_hook: Callable | None = None
)
```

| Method | What it does |
|---|---|
| `await connect(server_name, base_url, pinned_tools=[])` | Auto-discovers and registers all tools from an MCP server |
| `await disconnect(server_name)` | Closes connection, marks server DEAD |
| `await disconnect_all()` | Closes all connections |
| `register(server_name, tool_name, description, loader, tags=[], pinned=False)` | Manual registration for custom/static tools |
| `await ask(intent, params={})` | Main entry point — match, dispatch, return result |
| `available(intent)` | Dry-run match, returns candidates without dispatching |
| `health()` | Returns dict of server statuses + cache stats |

### `DispatchResult`

Returned by `ask()`.

```python
@dataclass
class DispatchResult:
    success: bool
    tool_key: str       # e.g. "brave::search"
    result: Any         # the actual tool output
    partial: bool       # True if stream died mid-response
    error_msg: str | None
```

### Errors

```python
from lazy_mcp import (
    ToolNotFoundError,    # tool_key not in registry
    ServerOfflineError,   # server marked DEAD at dispatch time
    PartialResultError,   # stream died mid-response, partial attached
    DispatchError,        # tool call threw, original exception at .cause
    NoMatchError          # matcher found nothing above threshold
)
```

---

## MCP compatibility

lazy-mcp speaks JSON-RPC 2.0 over HTTP, which is the MCP transport protocol. `connect()` calls `tools/list` on the server to auto-register, and dispatches via `tools/call`. This means it works in front of any spec-compliant MCP server without modification.

Tested against:
- Anthropic's reference MCP servers
- Custom servers implementing the JSON-RPC 2.0 + HTTP transport

SSE transport support: planned.

---

## Matching

Descriptions are private to lazy-mcp — the agent never sees them. This means you can write them as rich, keyword-dense strings without any concern for token cost:

```python
mcp.register(
    server_name="brave",
    tool_name="search",
    description="""
        web search, internet lookup, find URLs, browse online, 
        current events, news, fetch webpage, retrieve information,
        search engine, google, online research
    """,
    loader=my_loader
)
```

Match strategy order:

1. **Exact** — query matches tool name directly. Confidence 1.0.
2. **Keyword** — token overlap between query and description+tags. Confidence = matched/total tokens.
3. **Semantic** — only if exact+keyword both fail and a `semantic_hook` is registered. Hook receives query + all tools, returns ranked `MatchResult` list. Slot for an embedding model if you need it.

Threshold is configurable at init (`match_threshold=0.3`). Below threshold on all strategies → `NoMatchError`.

---

## Server health

Every server has a health state: `WARM | COLD | DEAD`.

- `WARM` — recently dispatched successfully
- `COLD` — registered but untested, or recovered from a failure
- `DEAD` — failed 3+ consecutive times (configurable via `DEFAULT_HEALTH_FAIL_LIMIT`)

Dispatching to a `DEAD` server raises `ServerOfflineError` immediately — no wasted call. Use `reset_health()` after a manual reconnect to move it back to `COLD`.

---

## LRU cache

Tracks warm tool connections. Default capacity: 32 entries.

```python
mcp.health()["cache"]
# {
#   "capacity": 32,
#   "size": 4,
#   "hits": 47,
#   "misses": 6,
#   "pinned": 1,
#   "hit_rate": 0.887
# }
```

Pin a tool to prevent it from ever being evicted:

```python
await mcp.connect("brave", "http://localhost:3000", pinned_tools=["search"])
# or at manual registration:
mcp.register(..., pinned=True)
```

---

## CLI

```bash
# inspect registered tools and server health
python -m lazy_mcp --config servers.yaml inspect

# manually fire a tool call
python -m lazy_mcp --config servers.yaml call brave::search '{"query": "test"}'
```

`servers.yaml` format:

```yaml
servers:
  - name: brave
    url: http://localhost:3000
    pinned: [search]
  - name: filesystem
    url: http://localhost:3001

lru_capacity: 32
match_threshold: 0.3
```

---

## Project structure

```
lazy_mcp/
├── __init__.py       # public exports only
├── gateway.py        # LazyMCP — the only class callers touch
├── registry.py       # hashmap + server health tracking
├── matcher.py        # intent → tool resolution
├── dispatcher.py     # dispatch, health updates, LRU population
├── lru.py            # generic LRU cache
├── mcp_compat.py     # MCP JSON-RPC transport, auto-discovery
├── models.py         # dataclasses: ToolEntry, DispatchResult, etc.
└── errors.py         # exception hierarchy
```

---

## What this is not

lazy-mcp is one module. It does not include:

- An LLM or any model
- Prompt construction or management
- Memory or conversation state
- Sandboxed execution
- A specific agent framework

It sits between your agent and your MCP servers. Everything else is your concern.

---

## License

MIT. Use it however you want, with or without attribution.

---

## Contributing

Issues and PRs welcome. If you're adding a semantic hook implementation (embeddings-based matching), open an issue first — there's a designated slot for it in `Matcher` and it should stay optional/zero-cost when unused.