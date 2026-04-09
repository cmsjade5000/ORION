# WIRE Firecrawl Pilot

Status: pending setup

## Purpose

Evaluate Firecrawl as an extract-first retrieval complement for WIRE without enabling the runtime plugin in this tranche.

Current blocker:
- `FIRECRAWL_API_KEY` is not configured in the live OpenClaw environment, so Firecrawl remains disabled.

## Readiness Check

```bash
python3 scripts/firecrawl_wire_pilot.py \
  --output-json tmp/firecrawl_wire_pilot_latest.json \
  --output-md tmp/firecrawl_wire_pilot_latest.md
```

What it checks:
- current `firecrawl` plugin status in the installed OpenClaw runtime
- current ClawHub search surface for Firecrawl-related skills
- validation steps and stop gates for WIRE-owned evaluation

## Pilot Scope

- WIRE remains the owner of evidence-backed retrieval
- links remain mandatory
- no runtime plugin enablement here
- no replacement of current browser/operator-pack posture by default

## Success Criteria

- improves crawl-grounded retrieval for docs/pages where current WIRE workflow is too manual
- preserves source links and operator-readable outputs
- does not lower trust boundaries or create retrieval ambiguity
