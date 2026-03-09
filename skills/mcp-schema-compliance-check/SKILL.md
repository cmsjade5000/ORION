---
name: mcp-schema-compliance-check
description: Validate MCP JSON messages against official protocol JSON schema to catch compatibility drift.
metadata:
  invocation: user
---

# MCP Schema Compliance Check

Use this skill to validate MCP JSON messages against the official protocol schema from `modelcontextprotocol/modelcontextprotocol`.

## Purpose

- Catch protocol compatibility drift early.
- Validate request/response payload samples before integration tests.
- Run the same schema check locally or in CI with explicit schema pinning.

## Prerequisites

- Bash 3.2+.
- Python available in PATH (default command: `python3`).
- Python package `jsonschema` installed, or use `--install`.
- Network access to fetch schema from GitHub raw (unless using a local `--schema-url`).

## One-Command Helper

```bash
bash skills/mcp-schema-compliance-check/scripts/run_mcp_schema_check.sh
```

## Schema Version Override Example

```bash
bash skills/mcp-schema-compliance-check/scripts/run_mcp_schema_check.sh \
  --schema-version 2025-06-18 \
  --input skills/mcp-schema-compliance-check/examples/ping_request.json
```

## Failure Interpretation

- `PASS` means the JSON file conforms to the selected MCP schema.
- `FAIL` means the payload does not match schema constraints (or cannot be parsed).
- Exit code is non-zero if any file fails.
- If dependency errors appear, install requirements or rerun with `--install`.
