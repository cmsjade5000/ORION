# Reliability Snapshot

- Generated at: `2026-04-30T16:24:57.561091+00:00`
- Window: last `24h`

## Lane Wait

- Count: `0`
- Max: `0 ms`
- P95: `0 ms`
- By lane: `{}`

## Cron

- Total / Enabled / Disabled: `34 / 4 / 30`
- By agent: `{'atlas': 1, 'main': 2, 'unknown': 1}`
- By delivery channel: `{'last': 3, 'none': 1}`

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
- Delivery status counts: `{'delivered': 5, 'not-requested': 4, 'not-delivered': 16}`

## Queue Health

- Status: `pass`
- Queued: `1`
- Pending verification: `0`
- Age buckets: `{'queued': {'state': 'queued', 'count': 1, 'stale_count': 0, 'stale_ratio': 0.0, 'missing_age_or_threshold': 1, 'age_min': None, 'age_max': None, 'age_mean': None, 'age_buckets': {'0-1h': 0, '1-4h': 0, '4-24h': 0, '>24h': 0}}, 'pending_verification': {'state': 'pending_verification', 'count': 0, 'stale_count': 0, 'stale_ratio': 0.0, 'missing_age_or_threshold': 0, 'age_min': None, 'age_max': None, 'age_mean': None, 'age_buckets': {'0-1h': 0, '1-4h': 0, '4-24h': 0, '>24h': 0}}}`
- Assertions: `[]`
- Growth: `{'previous': {'file': 'eval/history/reliability-20260410-141046.json', 'queued': None, 'pending_verification': None}, 'delta': {'queued_delta': 1, 'pending_verification_delta': 0}, 'delta_total_ratio': 1.0, 'slo_pass': False}`

## Delivery Queue

- Files: `0`
- By channel: `{}`
- Top errors: `[]`

## Eval Gate

- Status: `pass`
- Reasons: `[]`

## Queue Snapshot

- Source: `tasks/JOBS/summary.json`
- Counts: `{'queued': 1, 'pending_verification': 0, 'total_jobs': 8, 'workflow_count': 8}`
- Workflow count: `8`