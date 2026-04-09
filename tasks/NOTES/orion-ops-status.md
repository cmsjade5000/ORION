# ORION Incident Bundle

- Status: `degraded`
- Repo root: `/Users/corystoner/src/ORION`
- Bundle dir: `/Users/corystoner/src/ORION/tmp/incidents/20260408T034005-0400`
- Health OK: `False`
- Codex ready: `True`

## Gateway
- Health message: `Gateway Health`
- Runtime status: `running`
- RPC OK: `True`
- Config audit OK: `True`

## Channels
- Channel status OK: `False`
- States: `telegram=ok | discord=degraded | slack=disabled | mochat=off`

## Tasks
- Task list OK: `True`
- Task list count: `None`
- Task audit OK: `True`
- Task audit count: `None`

## Signals
- Discord restart indicators: `21`
- Telegram IPv4 fallback indicators: `0`
- Approval timeout indicators: `0`
- Kimi rate-limit indicators: `0`
- Stale task-ledger indicators: `0`
- Exec elevation failure indicators: `0`

## Commands
- `gateway_health`: `ok`
- `gateway_status`: `ok`
- `channels_status`: `ok`
- `doctor`: `ok`
- `tasks_list`: `ok`
- `tasks_audit`: `ok`
- `codex_version`: `ok`

## Artifacts
- `commands/*.txt|json`
- `gateway.log.tail.txt`
- `gateway.err.log.tail.txt`
- `summary.json`
