# Assistant Skill Ownership Matrix

This file defines the recommended skill and tool ownership map for the active ORION roster.

Categories:
- `default now`: expected part of the current posture
- `pending setup`: useful, but auth/setup/runtime proof is still required
- `pilot candidate`: worth testing, not part of default operation

## ORION

Default now:
- `mcporter`
- `task-packet-guard`
- `agentmail`
- `session-logs`
- `clawhub`

Pending setup:
- `social-intelligence`
- `phone-voice`

Pilot candidate:
- none

Live workflow:
- structured GitHub workflow expansion via `gh`-first structured reads

## ATLAS

Default now:
- `system-metrics`
- `gateway-service`
- `policy-gate-conftest`
- `secure-code-preflight`
- `secrets-scan`

Pending setup:
- none

Pilot candidate:
- none

Live workflow:
- ACPX specialist execution for bounded internal-only work
  Policy: native subagents stay default, ATLAS-owned only, Task Packets remain durable, `approve-reads` plus `nonInteractivePermissions=fail`, and `pluginToolsMcpBridge=false`

## WIRE

Default now:
- sources-first retrieval via repo/browser/evidence workflow
- `mcporter` for MCP-backed reads when available

Pending setup:
- Firecrawl retrieval workflow (`FIRECRAWL_API_KEY` required)

Pilot candidate:
- none

## POLARIS

Default now:
- `apple-notes`
- `apple-reminders`
- `things-mac`
- `agentmail`
- `task-packet-guard`
- `session-logs`

Pending setup:
- `apple-calendar-macos`
- `macos-contacts`

Pilot candidate:
- none

Live workflow:
- ClawHub-driven monthly admin-skill refresh

## SCRIBE

Default now:
- `scribe-draft-lint`
- `scribe-draft-tools`

Pending setup:
- none

Pilot candidate:
- none

## NODE

Default now:
- `task-packet-guard`
- `session-logs`

Pending setup:
- `mcporter`

Pilot candidate:
- none

## PULSE

Default now:
- `task-packet-guard`
- `session-logs`
- `postgres-job-queue`

Pending setup:
- none

Pilot candidate:
- `web-monitor`

## STRATUS

Default now:
- `system-metrics`
- `gateway-service`
- `secure-code-preflight`
- `supply-chain-verify-scan`

Pending setup:
- none

Pilot candidate:
- ACPX specialist execution pilot

## PIXEL

Default now:
- discovery and option-generation workflow
- `clawhub` for tool scouting

Pending setup:
- `social-intelligence`

Pilot candidate:
- curated discovery packs from ClawHub

## QUEST

Default now:
- gameplay guidance and progression support

Pending setup:
- none

Pilot candidate:
- none

## LEDGER

Default now:
- `ledger-finance`

Pending setup:
- none

Pilot candidate:
- none

## EMBER

Default now:
- `nonclinical-guardrails`

Pending setup:
- none

Pilot candidate:
- `phone-voice`

## Cross-Agent Situational Skills

- `social-intelligence`: pending setup; use only once auth is verified
- `web-monitor`: optional monitoring workflow, not a default capability claim
- `postgres-job-queue`: architecture pattern for durable background execution where Postgres already exists

## Maintenance

Monthly review workflow:

```bash
make toolset-audit
./scripts/assistant_skill_refresh.sh
```

Apply candidate updates only after review:

```bash
./scripts/assistant_skill_refresh.sh --apply
```

Use ClawHub as the standard discovery/update channel during review, but keep repo curation and policy review in the loop.
