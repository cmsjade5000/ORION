# ORION Error Review

Generated: 2026-04-11T06:19:39Z
Window: last 24h

## Summary
- Events scanned: 39
- Recurring groups: 6
- Fixes attempted: 11
- Fixes applied: 10

## Recurring Errors
- `06d03c2a3d62411c` [error] x3 :: timeout
- `87e4e8d9dfae6494` [error] x2 :: discord
- `8484e5f3d4cf671f` [error] x2 :: gateway
- `43e262afee0f1b4e` [error] x2 :: session
- `cff8764d8b7d8298` [error] x2 :: timeout
- `4e165eeb63e1064f` [warn] x2 :: gateway

## Safe Fix Attempts
- `openclaw config validate --json` -> exit 0
- `openclaw agents bindings --json` -> exit 0
- `openclaw plugins list --json` -> exit 0
- `openclaw hooks list` -> exit 0
- `openclaw gateway status --json` -> exit 0
- `python3 scripts/task_execution_loop.py --repo-root /Users/corystoner/src/ORION --apply --stale-hours 24` -> exit 0
- `python3 scripts/runtime_reconcile.py --repo-root /Users/corystoner/src/ORION --apply --json` -> exit 99
- `python3 scripts/task_registry_repair.py --repo-root /Users/corystoner/src/ORION --apply --json` -> exit 0
- `python3 scripts/session_maintenance.py --repo-root /Users/corystoner/src/ORION --agent main --fix-missing --apply --doctor --min-missing 1 --min-reclaim 1 --json` -> exit 0
- `openclaw channels status --probe --json` -> exit 0
- `openclaw channels logs --channel discord --json --lines 200` -> exit 0
