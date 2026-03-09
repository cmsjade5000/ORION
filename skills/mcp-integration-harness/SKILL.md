---
name: mcp-integration-harness
description: Build and validate minimal MCP server/client integration loops for ORION tool workflows.
metadata:
  invocation: user
---

# MCP Integration Harness

## Purpose And When To Use

Use this skill to prove a local MCP server/client loop works before wiring MCP tools into ORION workflows.

Use it when:
- Adding a new MCP server.
- Debugging tool discovery or call failures.
- Validating stdio transport behavior in CI or local dev.

## Prereqs

- Python 3.10+ and `pip`.
- Node 18+ only if using the MCP Inspector UI.

```bash
python3 -m pip install --upgrade pip
python3 -m pip install mcp
# Optional inspector UI
npx -y @modelcontextprotocol/inspector
```

## Minimal Local Smoke Test Workflow (Server/Client Roundtrip)

Create a tiny stdio server:

```python
# .tmp/mcp-harness/server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("smoke")

@mcp.tool()
def ping(text: str) -> str:
    return f"pong:{text}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Create a client that starts the server, initializes, lists tools, and calls `ping`:

```python
# .tmp/mcp-harness/client.py
import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    params = StdioServerParameters(
        command="python3",
        args=[".tmp/mcp-harness/server.py"],
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert any(tool.name == "ping" for tool in tools.tools)
            result = await session.call_tool("ping", {"text": "ok"})
            print(result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
```

Expected output:

```text
pong:ok
```

## Suggested Command Sequence To Run Checks

```bash
mkdir -p .tmp/mcp-harness
$EDITOR .tmp/mcp-harness/server.py
$EDITOR .tmp/mcp-harness/client.py
python3 .tmp/mcp-harness/client.py
# Optional visual inspection
npx -y @modelcontextprotocol/inspector
```

## One-command helper

```bash
bash skills/mcp-integration-harness/scripts/run_mcp_harness.sh
```

```bash
bash skills/mcp-integration-harness/scripts/run_mcp_harness.sh --inspect
```

## Validation Checklist

- Client `initialize()` succeeds.
- `list_tools()` returns expected tool names.
- `call_tool()` returns expected payload content.
- No extra stdout noise from server (stdio stays protocol-clean).
- If resources/prompts are implemented, verify they enumerate and resolve correctly.

## Failure Triage Checklist

- Confirm interpreter and package: `python3 --version` and `python3 -m pip show mcp`.
- Confirm transport and command path: `python3 .tmp/mcp-harness/server.py` runs without syntax/import errors.
- If client hangs, check for non-protocol prints/logging on stdout from the server.
- If tool calls fail, compare argument names/types with the tool signature.
- Re-run with clean env and debug logs when needed:

```bash
MCP_LOG_LEVEL=DEBUG python3 .tmp/mcp-harness/client.py
```
