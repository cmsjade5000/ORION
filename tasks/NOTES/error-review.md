# ORION Error Review

Generated: 2026-04-09T00:52:42Z
Window: last 24h

## Summary
- Events scanned: 150
- Recurring groups: 38
- Fixes attempted: 7
- Fixes applied: 7

## Recurring Errors
- `4e165eeb63e1064f` [error] x8 :: gateway
- `06d03c2a3d62411c` [error] x8 :: timeout
- `87e4e8d9dfae6494` [error] x4 :: discord
- `43e262afee0f1b4e` [error] x4 :: session
- `922f33a9aa609c04` [error] x3 :: 2026-04-06t11:52:03.228-04:00 [model-pricing] pricing bootstrap failed: error: openrouter /models failed: http 408
- `a832172ee42a60f8` [error] x3 :: 2026-04-07t20:05:37.025-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
- `7a9ce8f026008d9b` [error] x3 :: 2026-04-07t20:10:41.792-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
- `9aba6c7496b18c83` [error] x3 :: 2026-04-07t20:15:12.252-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
- `9d773f08ffb81389` [error] x3 :: 2026-04-07t20:20:33.545-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run
- `63cdb82a85455795` [error] x3 :: 2026-04-07t20:25:33.944-04:00 [openclaw] unhandled promise rejection: error: agent listener invoked outside active run

## Safe Fix Attempts
- `openclaw config validate --json` -> exit 0
- `openclaw agents bindings --json` -> exit 0
- `openclaw plugins list --json` -> exit 0
- `openclaw hooks list` -> exit 0
- `openclaw gateway status --json` -> exit 0
- `openclaw sessions cleanup --agent main --dry-run --fix-missing --json` -> exit 0
- `python3 scripts/task_execution_loop.py --repo-root /Users/corystoner/src/ORION --apply --stale-hours 24` -> exit 0
