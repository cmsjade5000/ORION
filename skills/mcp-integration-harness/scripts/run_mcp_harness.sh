#!/usr/bin/env bash
set -euo pipefail

python_cmd="python3"
workdir=".tmp/mcp-harness"
inspect=0

usage() {
  cat <<'EOF'
Usage: bash skills/mcp-integration-harness/scripts/run_mcp_harness.sh [options]

Options:
  --python <cmd>    Python command to run (default: python3)
  --workdir <path>  Working directory for smoke files (default: .tmp/mcp-harness)
  --inspect         Launch MCP Inspector after smoke test
  -h, --help        Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      if [[ $# -lt 2 ]]; then
        echo "Error: --python requires a value" >&2
        usage
        exit 1
      fi
      python_cmd="$2"
      shift 2
      ;;
    --workdir)
      if [[ $# -lt 2 ]]; then
        echo "Error: --workdir requires a value" >&2
        usage
        exit 1
      fi
      workdir="$2"
      shift 2
      ;;
    --inspect)
      inspect=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

mkdir -p "$workdir"

server_py="$workdir/server.py"
client_py="$workdir/client.py"

cat >"$server_py" <<'PY'
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("smoke")


@mcp.tool()
def ping(text: str) -> str:
    return f"pong:{text}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
PY

cat >"$client_py" <<'PY'
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
PY

output="$("$python_cmd" "$client_py" "$python_cmd" "$server_py" 2>&1)"
if ! printf '%s\n' "$output" | grep -Fq "pong:ok"; then
  echo "Smoke test failed: expected output to contain pong:ok" >&2
  printf '%s\n' "$output" >&2
  exit 1
fi

echo "MCP harness smoke test passed (pong:ok)."

if [[ "$inspect" -eq 1 ]]; then
  npx -y @modelcontextprotocol/inspector
fi
