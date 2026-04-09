# ORION Agent System Sweep 2026-04-07

Status: implemented documentation and test refresh

## What Changed

- Re-based ORION's documented posture on the live `2026.4.5` runtime instead of the March baseline.
- Tightened routing boundaries between PIXEL, WIRE, ATLAS, and POLARIS.
- Replaced the shallow skill shortlist with a per-agent ownership matrix.
- Added explicit pilot scaffolding for ClawHub workflow adoption, Firecrawl retrieval, ACPX specialist isolation, and structured GitHub expansion.
- Kept Task Packets as the durable async default.
- Enabled ACPX in the live runtime for bounded specialist execution.
- Promoted ClawHub and GitHub structured workflow usage from pilot status to live workflow status.
- Left Firecrawl pending setup because no `FIRECRAWL_API_KEY` is configured.

## What Remains Deferred

- Firecrawl plugin enablement
- Browser plugin enablement
- Treating dreaming as trusted durable memory

## Agent Tooling Posture

- ORION: routing, MCP inspection, task-packet validation, session history, skill discovery
- ATLAS: ops execution, policy gates, gateway diagnostics, safe implementation
- WIRE: evidence-first retrieval and retrieval pilots
- POLARIS: Apple/admin stack and queue hygiene
- SCRIBE: draft/lint/scaffold workflow
- NODE/PULSE/STRATUS: system glue, queue patterns, infra, and runtime health

See:
- `docs/ASSISTANT_SKILLS.md`
- `docs/ORION_RUNTIME_BASELINE_2026_04_07.md`
- `docs/ORION_TOOL_PILOTS_2026_04.md`

## Recommended Next Pilots

1. Firecrawl retrieval enablement after API key setup
2. Browser plugin evaluation against current operator-pack posture
3. ACPX usage validation on one real bounded specialist flow

## Acceptance Notes

- Setup-gated skills remain `pending setup`.
- Bundled-but-disabled runtime surfaces remain pilots, not live capabilities.
- Checked-in templates and live runtime state are documented separately on purpose.
