# ORION Tool Pilots 2026-04

Status: live workflow + remaining pilot scaffolding  
Scope: ACPX enabled live; Firecrawl still pending setup

## Summary

These pilots are the next bounded experiments after the April 2026 sweep. They are deliberately scoped so a later implementation pass can enable them without reopening product-policy decisions.

## Pilot 1: ClawHub Review Workflow

- Owner: ORION with policy review support from ATLAS
- Decision: live workflow
- Why: ClawHub-backed search/update is already available and is the cleanest standard path for monthly skill review
- Scope:
  - search for candidate updates
  - compare candidates against current repo-owned skills
  - review setup/auth/risk before any install/update
- Validation:
  - produce a shortlist with `default now`, `pending setup`, and `pilot candidate`
  - avoid bulk updates without review
- Stop gates:
  - any skill that expands external delivery surfaces
  - any skill that bypasses ORION's routing model
- Rollback:
  - none required for the audit-only workflow

Reference:
- `docs/CLAWHUB_SKILL_REFRESH_WORKFLOW.md`
- `python3 scripts/clawhub_skill_refresh.py --output-json tmp/clawhub_skill_refresh_latest.json --output-md tmp/clawhub_skill_refresh_latest.md`

## Pilot 2: WIRE Firecrawl Retrieval Pilot

- Owner: WIRE
- Decision: pending setup
- Why: Firecrawl is the clearest extract-first complement to current browser-heavy retrieval
- Scope:
  - document-grounded retrieval
  - crawl/search/scrape for evidence-first summaries
  - no default replacement of current browser/operator-pack posture
- Validation:
  - compare output quality, speed, and citation hygiene against current WIRE workflow
  - confirm it improves structured retrieval without lowering trust boundaries
- Stop gates:
  - requires new external delivery surfaces
  - encourages unsourced summaries or bypasses WIRE's evidence contract
- Rollback:
  - remove pilot docs and leave WIRE on current retrieval flow

Current blocker:
- `FIRECRAWL_API_KEY` is not configured in the live runtime.

Reference:
- `docs/WIRE_FIRECRAWL_PILOT.md`
- `python3 scripts/firecrawl_wire_pilot.py --output-json tmp/firecrawl_wire_pilot_latest.json --output-md tmp/firecrawl_wire_pilot_latest.md`

## Pilot 3: ACPX Specialist Pilot

- Owner: ATLAS
- Decision: live bounded execution surface
- Why: ACPX may improve bounded specialist isolation and plugin-tools MCP bridging for internal-only work
- Scope:
  - isolated specialist execution only
  - no replacement of native subagents as the default control path
  - no replacement of Task Packets as the durable async contract
  - no user-facing channel bypass
  - runtime stays pinned to read-approved, non-interactive-fail, bridge-disabled settings
- Validation:
  - prove ACPX adds concrete value over current `sessions_spawn` plus Task Packet flows
  - confirm plugin-tools MCP bridging is useful for bounded tasks
  - keep a passing bounded runtime smoke check in place
- Stop gates:
  - any design that turns ACPX into the default async model
  - any bypass of ORION-only ingress
  - any move to write-capable or unattended ACPX execution without a separate review
- Rollback:
  - remove `acpx` from the live allowlist and disable `plugins.entries.acpx.enabled`

Reference:
- `docs/ATLAS_ACPX_PILOT.md`
- `python3 scripts/acpx_pilot_check.py --output-json tmp/acpx_pilot_latest.json --output-md tmp/acpx_pilot_latest.md`
- `python3 scripts/acpx_runtime_smoke.py --output-json tmp/acpx_runtime_smoke_latest.json --output-md tmp/acpx_runtime_smoke_latest.md`

## Pilot 4: Structured GitHub Workflow Expansion

- Owner: ORION and ATLAS
- Decision: live workflow
- Why: current `gh` flows work, but some repo/PR/CI tasks are still manual and fragmented
- Scope:
  - repo/PR/CI/issue workflows
  - structured reads first
  - `gh` remains the stable fallback
- Validation:
  - demonstrate less manual parsing for PR checks, issue triage, and repository inspection
  - confirm no regression in explicit evidence/proof handling
- Stop gates:
  - replacing working `gh` flows without clear gain
  - introducing extra auth sprawl or opaque automation
- Rollback:
  - continue using the existing `github` skill and `gh` CLI

Reference:
- `docs/GITHUB_STRUCTURED_WORKFLOW_PILOT.md`
- `python3 scripts/github_structured_workflow_pilot.py --output-json tmp/github_structured_workflow_pilot_latest.json --output-md tmp/github_structured_workflow_pilot_latest.md`

## Deferred Candidates

- `browser` plugin: defer unless it materially improves over current managed-browser/operator-pack posture
- broad workflow platforms that bypass Task Packets: reject for now
- new delivery channels: reject for now unless tied to a concrete user need
