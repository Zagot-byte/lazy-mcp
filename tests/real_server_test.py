# real_server_test.py
import asyncio
from lazy_mcp import LazyMCP

async def main():
    mcp = LazyMCP()

    print("connecting...")
    await mcp.connect("fs", "http://localhost:3001")

    tools = mcp._registry.all_tools()
    print(f"\n{len(tools)} tools discovered:")
    for t in tools:
        print(f"  {t.tool_key}")

    print("\navailable() for 'read a file':")
    for c in mcp.available("read a file"):
        print(f"  {c.tool_key} conf={c.confidence:.2f} type={c.match_type}")

    print("\nask: list directory")
    result = await mcp.ask("list directory contents", {"path": "/tmp"})
    print(f"  success={result.success}")
    print(f"  tool={result.tool_key}")
    print(f"  result={str(result.result)[:120]}")

    print("\nhealth:")
    h = mcp.health()
    print(f"  fs status={h['servers']['fs']['status']}")
    print(f"  cache={h['cache']}")

    await mcp.disconnect_all()

asyncio.run(main())
