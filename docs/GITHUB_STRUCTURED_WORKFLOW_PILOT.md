# GitHub Structured Workflow Pilot

Status: live workflow

## Purpose

Use structured GitHub reads to complement the current `gh`-first workflow for repo, PR, issue, and CI work.

## Readiness Check

```bash
python3 scripts/github_structured_workflow_pilot.py \
  --output-json tmp/github_structured_workflow_pilot_latest.json \
  --output-md tmp/github_structured_workflow_pilot_latest.md
```

What it checks:
- `gh` availability
- current repo context
- auth status
- validation steps and stop gates for ORION/ATLAS usage

## Pilot Boundary

- `gh` remains the stable fallback
- pilot is read-heavy first
- no replacement of working `gh` commands without clear gain
- outputs must stay explicit and operator-readable

## Success Criteria

- less manual parsing for PR checks, issue context, and repository inspection
- no regression in proof/evidence handling
- no auth sprawl or opaque automation
