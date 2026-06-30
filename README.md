# lazy-mcp

Capability-based tool-dispatch middleware for LLM agents. Keeps tool schemas out of your prompt entirely.

---

## The problem

When an LLM agent has many registered tools, the standard approach dumps every tool's full schema into the system prompt on every call — name, description, parameters, examples, roughly 150–400 tokens each. Most of those tokens describe tools that won't be used in this call at all.

Recent research confirms this degrades both cost and accuracy as tool count grows. RAG-MCP (Gan et al., 2025) found that naive full-schema injection drops tool-selection accuracy to ~14% once a toolset grows large, and that retrieval-based filtering more than triples accuracy while cutting prompt tokens by over 50%. lazy-mcp pushes further: instead of retrieving and injecting a top-k set of schemas, the LLM never sees a schema at all.

### What lazy-mcp does

The LLM is given a flat, closed vocabulary of **capability labels** — not tool names, not descriptions, not schemas:

```
Available capabilities: file_access, web_search, code_execution
```

That's the entire discovery surface. Tens of tokens, fixed regardless of how many tools or servers sit behind each label. To use a tool, the LLM expresses intent against one capability:

```json
{"capability": "file_access", "task": "read matcher.py", "params": {"path": "matcher.py"}}
```

lazy-mcp resolves the capability to the set of installed tools that provide it, ranks them by relevance to `task` using BM25, dispatches the best match, and returns only the result. Schema cost to the agent: zero, always.

---

## How it works

```
Agent
  │  {"capability": "file_access", "task": "read matcher.py"}
  ▼
lazy-mcp
  ├── Stage 1: filter tools by capability (exact match, closed vocabulary)
  ├── Stage 2: BM25-rank remaining candidates against task text
  ├── health check → is this server alive?
  ├── LRU check → is this tool warm?
  └── dispatch → MCP server → result
  │
  ▼
Agent
  │  result only — never a schema, ever
```

Core structures:

- **Hashmap** — `tool_key → ToolEntry` (`server_name::tool_name`), holding a rich description and a closed set of capability labels. Private to lazy-mcp; the agent never sees it.
- **Capability vocabulary** — the only thing exposed to the LLM. A flat, deduplicated list of labels across all registered tools.
- **BM25 ranking** — when multiple tools share a capability, the task text is matched against each tool's description using BM25Okapi, a standard, well-tested information-retrieval ranking function. No embeddings, no model dependency.
- **LRU cache** — tracks warm tool/server connections for fast repeat dispatch. Does not cache results.

---

## Install

```bash
pip install lazy-mcp
```

Or from source:

```bash
git clone https://github.com/YOUR_HANDLE/lazy-mcp
cd lazy-mcp
pip install -e .
```

**Requires:** Python 3.11+, `aiohttp`, `rank-bm25`

---

## Quickstart

### Manual registration

```python
import asyncio
from lazy_mcp import LazyMCP

async def read_file_handler(params: dict):
    with open(params["path"]) as f:
        return f.read()

async def main():
    mcp = LazyMCP()

    mcp.register(
        server_name="local",
        tool_name="read_file",
        description="read file open local disk contents filesystem path",
        loader=read_file_handler,
        tags=["read", "file", "disk"],
        capabilities=["file_access"]
    )

    # what the LLM is allowed to see
    print(mcp.capabilities())   # ["file_access"]

    result = await mcp.ask(
        capability="file_access",
        task="read matcher.py",
        params={"path": "matcher.py"}
    )

    print(result.success, result.result)

asyncio.run(main())
```

### As a hosted server

If you're hosting an agentic tool and want any lazy-mcp-aware client to use it without seeing your schemas:

```python
from lazy_mcp import serve
import asyncio

server = serve(port=8000)

server.register(
    tool_name="search",
    description="search web internet lookup find URLs browse online",
    handler=my_search_handler,
    tags=["search", "web"],
    capabilities=["web_search"]
)

asyncio.run(server.start())
```

```bash
curl http://localhost:8000/capabilities
# {"capabilities": ["web_search"]}

curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"capability": "web_search", "task": "find info on lazy evaluation", "params": {"query": "lazy evaluation python"}}'
```

`/tools/list` is also exposed for standard MCP clients, returning minimal descriptors (no full schemas).

---

## API

### `LazyMCP`

| Method | What it does |
|---|---|
| `await connect(server_name, base_url, pinned_tools=[])` | Auto-discovers and registers tools from a live MCP server (capability tagging on auto-discovered tools is a known gap — see below) |
| `register(server_name, tool_name, description, loader, tags=[], capabilities=[], pinned=False)` | Manual registration with closed-vocabulary capability labels |
| `capabilities()` | Returns the flat list of capability labels — this is what you show the LLM |
| `await ask(capability, task, params={})` | Two-stage match (capability filter → BM25 rank) → dispatch → result |
| `available(capability, task)` | Dry-run match, no dispatch |
| `health()` | Server statuses + cache stats |

### `DispatchResult`

```python
@dataclass
class DispatchResult:
    success: bool
    tool_key: str
    result: Any
    partial: bool
    error_msg: str | None
```

### Errors

```python
from lazy_mcp import (
    ToolNotFoundError, ServerOfflineError, PartialResultError,
    DispatchError, NoMatchError
)
```

`NoMatchError` is raised when the capability doesn't exist, or when no candidate clears the match threshold for the given task.

---

## Matching

A tool only becomes a candidate if it's tagged with the requested capability — this is a hard filter, not a ranking signal. BM25 only ranks *within* that filtered set, disambiguating between multiple tools that share a capability (e.g. two different file-read implementations).

```python
mcp.register(
    server_name="local", tool_name="read_local",
    description="read file from local disk filesystem path contents",
    loader=local_handler, capabilities=["file_access"]
)
mcp.register(
    server_name="s3", tool_name="read_remote",
    description="read object from S3 bucket cloud storage key",
    loader=s3_handler, capabilities=["file_access"]
)
```

Both share `file_access`. A task like `"read the config from S3"` will BM25-rank `read_remote` higher due to "S3"/"bucket" term overlap; `"read local config"` ranks `read_local` higher.

Match threshold is configurable (`match_threshold=0.3` default). On very small candidate sets where BM25's IDF term can degenerate to zero, the matcher falls back to raw term-overlap counting rather than returning a false miss.

A `semantic_hook` slot exists for plugging in embedding-based matching later; unused by default, zero runtime cost when not set.

---

## Server health & LRU

Same as before — servers track `WARM | COLD | DEAD` status, with `DEAD` triggering immediate `ServerOfflineError` on dispatch. The LRU cache (configurable capacity, default 32) tracks warm tool connections, not cached results — every dispatch calls the loader fresh with real params.

```python
mcp.health()
# {
#   "total_tools": 4,
#   "servers": {"local": {"status": "warm", "fail_count": 0}},
#   "cache": {"capacity": 32, "size": 2, "hits": 5, "misses": 2, "hit_rate": 0.71}
# }
```

---

## Known gaps

- **Auto-discovery capability tagging** — `connect()` pulls tool schemas from live MCP servers via `tools/list`, but the MCP protocol has no capability field. Auto-discovered tools currently need capability labels assigned manually after `connect()`. A proper inference or mapping layer is planned.
- **SSE transport** — `mcp_compat.py` currently speaks HTTP JSON-RPC POST only.
- **Multi-capability tasks** — a single `ask()` call resolves one capability. Composite intents ("read this file and summarize it") aren't decomposed automatically.

---

## Prior work

lazy-mcp's token-reduction approach is closely related to RAG-MCP (Gan et al., arXiv:2505.03275), which retrieves a top-k subset of full tool schemas via semantic search before injecting them into the prompt. lazy-mcp differs in two ways: matching is deterministic (BM25, not embeddings) by default, and the LLM never sees a schema at all — only a closed capability vocabulary and the final result.

---

## License

MIT.

---

## Contributing

Issues and PRs welcome. The auto-discovery capability mapping gap above is a good first contribution if you want to dig in.
