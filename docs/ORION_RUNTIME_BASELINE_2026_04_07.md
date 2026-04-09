# ORION Runtime Baseline 2026-04-07

Status: current baseline memo  
Scope: repo-grounded and runtime-grounded April 2026 posture refresh

## Summary

This memo replaces the stale assumptions from the March 2026 capability intake and toolset adoption notes when evaluating ORION's current agent/tool posture.

Key current-state facts:
- Live OpenClaw runtime is `2026.4.5`.
- Live runtime config differs from the checked-in template in important ways.
- ClawHub-backed skill discovery is available now.
- `acpx` is enabled in the active runtime for bounded specialist execution.
- `browser` and `firecrawl` exist as bundled runtime surfaces but are not allowlisted in the active runtime.
- Checked-in templates remain conservative and should stay separate from live runtime facts.

## Documented vs Runtime vs Recommended

| Area | Checked-in template/docs | Live runtime on 2026-04-07 | Recommended stance |
| --- | --- | --- | --- |
| OpenClaw version | Historical docs still emphasize `2026.3.13` upgrade notes | `OpenClaw 2026.4.5` | Treat `2026.3.13` docs as history, not current baseline |
| Memory slot | Template default is `memory-lancedb` | Runtime slot is `memory-core` | Keep template conservative; document runtime separately |
| Dreaming | Template keeps dreaming disabled | Runtime has dreaming enabled | Keep pilot framing in repo docs; do not imply auto-trusted memory |
| ClawHub | March docs treat it as an intake/pilot topic | `openclaw skills list` exposes ClawHub-backed discovery now | Adopt as the default skill discovery/update workflow |
| ACPX | Not part of checked-in allowlist | Bundled in runtime, enabled in live config | Treat as a bounded live execution surface for ATLAS-owned specialist work |
| Browser plugin | Current browser posture is operator-pack and managed-browser guidance | Bundled in runtime, disabled by allowlist | Defer unless it materially outperforms current managed-browser flows |
| Firecrawl plugin | Mentioned as a candidate in March notes | Bundled in runtime, disabled by allowlist | Strongest retrieval pilot candidate for WIRE |
| OpenProse | Enabled in templates and runtime | Enabled | Keep as optional workflow formalization, not the durable default async primitive |
| Async work model | Some docs still mention `sessions_yield` as preference | Durable repo reality remains Task Packet plus reconcile loops | Keep Task Packets as the default async contract |

## Runtime Evidence Snapshot

- `openclaw --version` -> `OpenClaw 2026.4.5`
- `openclaw config validate --json` -> valid runtime config
- `openclaw config get plugins` -> active allowlist includes `telegram`, `discord`, `slack`, `open-prose`, `minimax`, `google`, `openrouter`, `openai`
- `openclaw config get plugins` -> active memory slot is `memory-core`
- `openclaw plugins list --json` -> `memory-core` loaded, `acpx` loaded, `browser`/`firecrawl` bundled but disabled by allowlist
- `openclaw skills list` -> ClawHub skill surface available

## Routing and Ownership Implications

- ORION remains the only user-facing ingress.
- ATLAS remains the operational director.
- WIRE owns evidence-first external retrieval.
- PIXEL owns discovery and tool scouting, not source-of-record retrieval.
- POLARIS remains the admin orchestrator.
- Task Packets remain the default durable async primitive until a better operational model is proven.

## Audit Command

Use the reproducible non-mutating audit path:

```bash
make toolset-audit
```

Artifacts:
- `tmp/orion_toolset_audit_latest.json`
- `tmp/orion_toolset_audit_latest.md`

## Relationship To Historical Docs

- `docs/OPENCLAW_CAPABILITY_INTAKE_2026_03_18.md` is historical intake context.
- `docs/ORION_TOOLSET_ADOPTION_2026_03_22.md` is a historical recommendation set.
- This memo is the April 2026 baseline that later docs in this tranche should follow.
