SHARED CONTEXT (paste above)

Write lazy_mcp/mcp_compat.py.
Imports: asyncio, json, time, typing
         aiohttp                          (only third-party import allowed here)
         lazy_mcp.models (ToolEntry, ServerHealth, HealthStatus)
         lazy_mcp.errors (ServerOfflineError)

MCP protocol note:
  MCP servers communicate via JSON-RPC 2.0 over HTTP.
  Every request body shape:
    {"jsonrpc": "2.0", "id": <int>, "method": "<method>", "params": <dict>}
  tools/list response shape:
    {"result": {"tools": [{"name": str, "description": str, 
                           "inputSchema": dict}, ...]}}
  tools/call response shape:
    {"result": {"content": [{"type": str, "text": str}]}}

Write one class: MCPConnection

Fields:
  server_name: str
  base_url: str                  # e.g. "http://localhost:3000"
  _session: aiohttp.ClientSession | None    # default None
  _request_counter: int          # for JSON-RPC id field, starts at 0

Methods:

  async def connect(self) -> None:
    """
    Open aiohttp.ClientSession. Store in _session.
    Raise ServerOfflineError if connection cannot be established.
    """

  async def close(self) -> None:
    """Close _session if open. Set to None."""

  async def list_tools(self) -> list[dict]:
    """
    POST to base_url with method "tools/list", params={}.
    Increment _request_counter for the id field.
    Return the list at response["result"]["tools"].
    Raise ServerOfflineError on HTTP error or timeout.
    """

  async def call_tool(self, tool_name: str, params: dict) -> Any:
    """
    POST to base_url with method "tools/call", 
    params={"name": tool_name, "arguments": params}.
    Return response["result"]["content"] directly.
    Raise ServerOfflineError on HTTP error or timeout.
    Raise PartialResultError if response has no "result" key 
    (stream died mid-response).
    """

  def make_loader(self, tool_name: str) -> Callable:
    """
    Return an async closure that calls self.call_tool(tool_name, params).
    Signature of returned closure: async def loader(params: dict) -> Any
    This is what gets stored as ToolEntry.loader at registration time.
    """

  def _next_id(self) -> int:
    """Increment _request_counter and return it."""


Write one standalone async function outside the class:

async def discover(server_name: str, base_url: str, 
                   registry) -> MCPConnection:
  """
  Full auto-registration flow:

  1. Create MCPConnection(server_name, base_url).
  2. await connection.connect()
  3. tools = await connection.list_tools()
  4. For each tool in tools:
       loader = connection.make_loader(tool["name"])
       registry.register(
         server_name = server_name,
         tool_name   = tool["name"],
         description = tool["description"],
         loader      = loader,
         tags        = []          # extracted from inputSchema keys as bonus:
                                   # tags = list(tool.get("inputSchema", {})
                                   #              .get("properties", {}).keys())
       )
  5. Return the MCPConnection so caller can close it later.

  registry parameter is typed as Any to avoid circular import — 
  the actual type is ToolRegistry.
  """