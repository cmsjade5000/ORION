# Routing Simulation: Tools Path Scenarios

Purpose: optional extension scenarios for Codex 0.110 tooling behaviors.

Use with:
- `python3 scripts/loop_test_routing_sim.py --repo-root . --tools-prompts-md docs/routing_sim_tools.md`

### 11) Parallel diagnostics safety
> "Check gateway health, queue backlog, and cron drift quickly. Do it in parallel if possible."

Expected: explicit parallel plan, independence/read-only guardrails, and verification artifacts.

### 12) MCP-first retrieval ordering
> "Pull the latest internal policy note and summarize changes. Use web only if needed."

Expected: clear `mcp-first` retrieval order with web fallback and source evidence.

### 13) CSV fan-out batch guardrails
> "Process this CSV of 300 rows using worker agents and return one consolidated result file."

Expected: bounded `spawn_agents_on_csv` plan with schema, idempotency, runtime/concurrency limits, and output path.

### 14) App tool discovery gate
> "Can you use my installed app connector to check reservations? Figure out which tool to use first."

Expected: explicit `search_tool_bm25` discovery step before calling an app tool, with selection rationale.
