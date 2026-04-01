# ORION Incident Bundle

- Status: `degraded`
- Repo root: `/Users/corystoner/src/ORION`
- Bundle dir: `/Users/corystoner/src/ORION/tmp/incidents/20260331T222355-0400`
- Health OK: `False`
- Codex ready: `True`

## Gateway
- Health message: `Gateway Health`
- Runtime status: `running`
- RPC OK: `True`
- Config audit OK: `False`

## Channels
- Channel status OK: `False`
- States: `telegram=ok | discord=degraded | slack=disabled | mochat=off`

## Tasks
- Task list OK: `True`
- Task list count: `114`
- Task audit OK: `True`
- Task audit count: `30`

## Signals
- Discord restart indicators: `8`
- Telegram IPv4 fallback indicators: `7`
- Approval timeout indicators: `0`
- Kimi rate-limit indicators: `43`
- Stale task-ledger indicators: `1`
- Exec elevation failure indicators: `2`

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
