# ATLAS ACPX Pilot

Status: live bounded execution surface

## Purpose

Use ACPX for bounded specialist execution while keeping native subagents as the default delegation path, ORION ingress unchanged, and Task Packet durability intact.

## Live Verification

```bash
python3 scripts/acpx_pilot_check.py \
  --output-json tmp/acpx_pilot_latest.json \
  --output-md tmp/acpx_pilot_latest.md
```

What it checks:
- installed runtime status for `acpx`
- live config allowlist and bounded ACPX settings
- current local MCP surface via `mcporter`
- validation steps and stop gates for ATLAS-owned bounded usage

Runtime smoke:

```bash
python3 scripts/acpx_runtime_smoke.py \
  --output-json tmp/acpx_runtime_smoke_latest.json \
  --output-md tmp/acpx_runtime_smoke_latest.md
```

What the smoke test enforces:
- `acpx` is present in the live plugin allowlist
- `plugins.entries.acpx.enabled=true`
- plugin status is `loaded`
- `cwd=/Users/corystoner/src/ORION`
- `permissionMode=approve-reads`
- `nonInteractivePermissions=fail`
- `pluginToolsMcpBridge=false`

## Pilot Boundary

- ATLAS owns the pilot
- ATLAS owns the live ACPX lane
- specialist execution only
- native `sessions_spawn` plus `sessions_yield` remains the default control path for ORION-core delegation
- Task Packets remain the durable async contract
- no ORION ingress bypass
- no direct user-facing ACPX usage
- no write-capable or unattended ACPX expansion
- plugin-tools MCP bridging stays off until separately approved and tested

## Success Criteria

- ACPX shows concrete value over current `sessions_spawn` plus Task Packet usage
- plugin-tools bridging, if later tested, stays bounded and deliberate
- no ambiguity about who owns execution, state, or user communication
