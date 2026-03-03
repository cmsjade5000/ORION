---
name: openprose-canary
description: Staging-only canary wrapper for evaluating OpenProse workflow usage in ORION.
---

# OpenProse Canary (Staging Only)

Use this skill only during staged canary validation.

## Constraints

- Do not use in production response paths.
- Do not trigger outbound channel sends from this skill.
- Always run pre and post eval checks.

## Procedure

1. Run baseline gate:
   - `make eval-compare BASE=eval/history/baseline-2026-03.json AFTER=eval/latest_report.json`
2. If gate passes, run the planned OpenProse test workflow in an isolated session.
3. Re-run:
   - `make eval-run`
4. Log results in:
   - `/Users/corystoner/src/ORION/docs/skills/canary-results-2026-03.md`

If any gate fails, set candidate status to `hold` and stop.
