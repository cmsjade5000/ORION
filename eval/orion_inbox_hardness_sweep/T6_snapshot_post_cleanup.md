# Reliability Snapshot

- Generated at: `2026-04-27T15:21:54.042738+00:00`
- Window: last `24h`

## Lane Wait

- Count: `4`
- Max: `73792 ms`
- P95: `55215 ms`
- By lane: `{'session:agent:main:main': 4}`

## Cron

- Total / Enabled / Disabled: `34 / 1 / 33`
- By agent: `{'unknown': 1}`
- By delivery channel: `{'none': 1}`

## Inbox Queue Contract

- Contract status: `pass`
- Canonical job present: `False`
- Canonical job enabled: `True`
- Canonical session target: `launchagent`
- Canonical delivery mode: `launchagent`
- Legacy queue jobs present: `[]`
- Legacy queue jobs enabled: `[]`
- Contract assertions: `[]`

## Job State (`jobs-state.json`)

- Version: `1`
- Total: `34`
- By last status: `{'ok': 30, 'error': 2}`
- Delivery status counts: `{'delivered': 5, 'not-delivered': 17, 'not-requested': 2}`

## Queue Health

- Status: `pass`
- Queued: `8`
- Pending verification: `4`
- Age buckets: `{'queued': {'state': 'queued', 'count': 8, 'stale_count': 0, 'stale_ratio': 0.0, 'missing_age_or_threshold': 8, 'age_min': None, 'age_max': None, 'age_mean': None, 'age_buckets': {'0-1h': 0, '1-4h': 0, '4-24h': 0, '>24h': 0}}, 'pending_verification': {'state': 'pending_verification', 'count': 4, 'stale_count': 0, 'stale_ratio': 0.0, 'missing_age_or_threshold': 4, 'age_min': None, 'age_max': None, 'age_mean': None, 'age_buckets': {'0-1h': 0, '1-4h': 0, '4-24h': 0, '>24h': 0}}}`
- Assertions: `[]`
- Growth: `{'previous': {'file': '/Users/corystoner/src/ORION/eval/history/reliability-20260427-151801.json', 'queued': 29, 'pending_verification': 4}, 'delta': {'queued_delta': -21, 'pending_verification_delta': 0}, 'delta_total_ratio': -0.6364, 'slo_pass': False}`

## Delivery Queue

- Files: `0`
- By channel: `{}`
- Top errors: `[]`

## Eval Gate

- Status: `pass`
- Reasons: `[]`

## Queue Snapshot

- Source: `/Users/corystoner/src/ORION/tasks/JOBS/summary.json`
- Counts: `{'queued': 8, 'pending_verification': 4, 'total_jobs': 33, 'workflow_count': 9}`
- Workflow count: `9`