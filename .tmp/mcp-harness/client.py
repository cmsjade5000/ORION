import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: client.py <python_cmd> <server_path>")
    command = sys.argv[1]
    server_path = sys.argv[2]
    params = StdioServerParameters(command=command, args=[server_path])
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert any(tool.name == "ping" for tool in tools.tools)
            result = await session.call_tool("ping", {"text": "ok"})
            print(result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
