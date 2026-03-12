# Codex Tool Capability Map (ORION, 0.114+ Baseline)

Purpose: map current Codex/OpenClaw tool paths to Gateway ownership, allowed usage, and verification requirements.

Last updated: 2026-03-12 (America/New_York)

Historical note: this file keeps the `CODEX_0110` name for backlink stability, but the contents track the current runtime baseline.

## Scope

- This map applies to ORION runtime orchestration in this repository.
- It does not override `SECURITY.md`, `TOOLS.md`, or agent SOUL contracts.
- When policies conflict, `SECURITY.md` wins.

## Ownership Matrix

| Tool | Primary Owner | Typical Use | Side-Effect Class | Required Evidence |
| --- | --- | --- | --- | --- |
| `sessions_spawn` | ORION (or ATLAS for ops sub-agents) | Primary specialist delegation and result collection in Gateway runtime | read/write (depends on delegated task) | Task Packet + specialist `Result:` summary + evidence path |
| `spawn_agent`, `send_input`, `wait`, `close_agent` | ORION/ATLAS (Codex desktop execution contexts) | Local Codex sub-agent orchestration when `sessions_spawn` is unavailable | read/write (depends on delegated task) | task scope + specialist output summary |
| `multi_tool_use.parallel` | ORION, ATLAS | Parallel read/diagnostic checks and independent verifications | read-only by default | command list + consolidated output summary |
| `list_mcp_resources`, `list_mcp_resource_templates`, `read_mcp_resource` | WIRE (retrieval), ORION (fallback) | Source-backed retrieval from configured MCP servers | read-only | source URI + short extraction summary |
| `search_tool_bm25` | ORION | Discover app MCP tools before app task execution | read-only | discovered tool names + chosen tool rationale |
| `js_repl`, `js_repl_reset` | ATLAS/STRATUS (ops), ORION (diagnostics) | Node-based diagnostics, data transforms, script prototyping | read-only unless writing files intentionally | executed snippet intent + output summary |
| `spawn_agents_on_csv` (if enabled) | ATLAS or POLARIS via ATLAS | Bounded batch work with one worker per row | write-capable; treat as high coordination risk | input CSV path + schema + aggregate result CSV path |
| `view_image` | ORION, PIXEL | Inspect local image artifacts and screenshots | read-only | file path + interpretation summary |

## Policy Rules

1. Prefer MCP retrieval before web search when the needed source exists in MCP.
2. Use `multi_tool_use.parallel` only when tasks are independent and non-destructive.
3. Use `sessions_spawn` as the default delegation path in Gateway runtime; use `spawn_agent/send_input/wait/close_agent` only in local Codex execution contexts.
4. Use `spawn_agents_on_csv` only with explicit schema, runtime limits, and idempotent row instructions.
5. Any write-capable tool flow must include rollback or containment notes in the Task Packet.
6. ORION remains the only user-facing synthesizer; specialist tool outputs are internal inputs.

## Delegation Guardrails

- ORION -> ATLAS for operational workflows, infra, and multi-step tool execution.
- ORION -> POLARIS for admin workflows; POLARIS -> ATLAS for execution.
- ORION may execute directly only when action is single-step, reversible, low-risk, and verifiable same turn.
- For risky/destructive actions, ask for explicit confirmation before execution.

## Verification Checklist

- Record command/tool invocations used.
- Record material outputs (report path, diff path, or artifact path).
- Distinguish `queued` / `in progress` / `pending verification` / `complete`.
- Do not claim completion without execution evidence in-turn or specialist `Result:`.
