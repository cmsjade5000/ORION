# Repo Hygiene

This repo works best when Git tracks **source-of-truth files** and ignores **runtime state**.

## Keep Versioned

- source code under `src/`, `apps/`, `scripts/`, `db/`
- agent definitions and generated SOULs
- canonical docs and runbooks under `docs/`
- checked-in config templates such as `openclaw.json.example` and `openclaw.yaml`
- stable reference artifacts such as named eval baselines
- curated memory files like `MEMORY.md`, `memory/WORKING.md`, and intentionally maintained daily notes

## Ignore As Local Runtime State

- delegated-job snapshots under `tasks/JOBS/*.json`
- generated operator notes under `tasks/NOTES/assistant-agenda.md`, `error-review.md`, `operator-health-bundle.md`, `orion-ops-status.md`, `runtime-reconcile.md`, `session-maintenance.md`, `status.md`, and `plan.md`
- dreaming ingestion/output under `memory/.dreams/`
- timestamped eval churn such as lane-hotspots, reliability, route-hygiene, stop-gate, and policy-gate history outputs
- generated benchmark event logs such as `eval/provider_benchmark_events.jsonl`
- archived session-memory artifacts under `tasks/WORK/artifacts/session-memory-archive/`

## Move Out Of Day-To-Day Branches

If you want long-lived historical retention, keep it outside the normal working branch:

- large timestamped eval/report histories
- session-memory archives
- ad hoc ops bundles or debugging dumps

Good homes are:

- `tmp/` for disposable local artifacts
- a separate archive branch/worktree
- external storage if the artifact matters operationally but not as source code

## Rule Of Thumb

If ORION can regenerate it from current state, scheduler runs, or diagnostics, it should usually be ignored rather than versioned.
