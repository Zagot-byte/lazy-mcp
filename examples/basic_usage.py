# requires a running MCP server at localhost:3000
# for local testing, set base_url to a mock or use the manual register() path

import asyncio
from lazy_mcp import LazyMCP


async def main() -> None:
    mcp = LazyMCP()

    try:
        # 1. Auto-discover and register all tools from the MCP server
        await mcp.connect("brave", "http://localhost:3000")

        # 2. Check available tools for intent
        matches = mcp.available("search the web")
        print("Available matches:")
        for m in matches:
            print(f"  {m.tool_key} (confidence={m.confidence:.2f}, type={m.match_type.value})")

        # 3. Dispatch the best match with params
        result = await mcp.ask("search the web", {"query": "lazy evaluation python"})
        print(f"\nDispatch result:")
        print(f"  success={result.success}")
        print(f"  tool_key={result.tool_key}")
        print(f"  result={result.result}")

        # 4. Check system health
        health = mcp.health()
        print(f"\nSystem health:")
        print(f"  total_tools={health['total_tools']}")
        for server, info in health["servers"].items():
            print(f"  {server}: status={info['status']}, fails={info['fail_count']}, tools={info['tools']}")
        print(f"  cache={health['cache']}")

    finally:
        # 5. Clean up all connections
        await mcp.disconnect_all()


if __name__ == "__main__":
    asyncio.run(main())
