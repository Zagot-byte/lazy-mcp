SHARED CONTEXT (paste above)

Update examples/basic_usage.py to show this flow INSTEAD of manual register():

1. Instantiate LazyMCP()
2. await mcp.connect("brave", "http://localhost:3000")
   — this calls tools/list on the server, auto-registers everything
3. Call mcp.available("search the web") and print matches
4. Call await mcp.ask("search the web", {"query": "lazy evaluation python"})
   and print result
5. Call mcp.health() and print it
6. await mcp.disconnect_all() in a finally block

Wrap everything in asyncio.run(main()).
Add a comment at the top:
  # requires a running MCP server at localhost:3000
  # for local testing, set base_url to a mock or use the manual register() path