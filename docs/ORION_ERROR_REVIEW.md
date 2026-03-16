# ORION Error Review

ORION now keeps a repo-local operational error database in:

- `db/orion-ops.sqlite`

This is the machine-oriented layer for recurring failures. It complements, but does not replace:

- `tasks/INCIDENTS.md` for human/audited incidents
- `tasks/QUEUE.md` and `tasks/INBOX/*.md` for follow-up work

## Why A Separate DB

- Repeated runtime/script/packet failures are noisy and structured.
- Incidents should stay short and high-signal.
- A sqlite DB supports dedupe, recurrence tracking, and nightly review without bloating memory files.

## Script

Primary entrypoint:

```bash
python3 scripts/orion_error_db.py stats --json
python3 scripts/orion_error_db.py review --window-hours 24 --json
python3 scripts/orion_error_db.py review --window-hours 24 --apply-safe-fixes --escalate-incidents --json
```

## Review Model

Nightly review does three things:

1. Ingest machine-relevant failures from:
   - `tasks/INCIDENTS.md`
   - failed/blocked Task Packets in `tasks/INBOX/*.md`
   - recent gateway error logs
2. Group recurring failures by fingerprint
3. Run a small allowlist of safe local checks/fixes, then escalate recurring error-level issues into `tasks/INCIDENTS.md`

## Safe Fix Allowlist

Current safe review commands:

- `openclaw config validate --json`
- `openclaw agents bindings --json`
- `openclaw plugins list --json`
- `openclaw hooks list`
- `openclaw gateway status --json`
- `openclaw sessions cleanup --agent main --dry-run --fix-missing --json`
- `python3 scripts/task_execution_loop.py --repo-root . --apply --stale-hours 24`

These are intentionally bounded. Nightly review should not perform broad/destructive remediations.

## Deliberate Session Maintenance

Session cleanup is intentionally split from error review.

Use:

```bash
python3 /Users/corystoner/src/ORION/scripts/session_maintenance.py --repo-root /Users/corystoner/src/ORION --agent main --fix-missing --json
AUTO_OK=1 python3 /Users/corystoner/src/ORION/scripts/session_maintenance.py --repo-root /Users/corystoner/src/ORION --agent main --fix-missing --apply --doctor --min-missing 50 --min-reclaim 25 --json
```

This writes:

- `tasks/NOTES/session-maintenance.md`

and only applies cleanup when drift crosses the configured thresholds.

## Cron

The assistant cron installer includes:

- `orion-error-review`
- `orion-session-maintenance`

It runs nightly in an isolated main-agent session and writes a report to:

- `tasks/NOTES/error-review.md`
- `tasks/NOTES/session-maintenance.md`

## Degraded vs Failed

When triaging ORION:

- `failed` means the gateway or required probes are down
- `degraded` means the gateway is up but config audit, RPC reachability, or related health checks are not fully clean

Use:

```bash
scripts/stratus_healthcheck.sh
```

to get the current classification.
