from mcp.server.fastmcp import FastMCP

mcp = FastMCP("smoke")


@mcp.tool()
def ping(text: str) -> str:
    return f"pong:{text}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
