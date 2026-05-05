# Reliability Snapshot

- Generated at: `2026-05-05T14:10:17.853559+00:00`
- Window: last `24h`

## Lane Wait

- Count: `0`
- Max: `0 ms`
- P95: `0 ms`
- By lane: `{}`

## Cron

- Total / Enabled / Disabled: `35 / 5 / 30`
- By agent: `{'main': 4, 'unknown': 1}`
- By delivery channel: `{'last': 4, 'none': 1}`

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
- Total: `35`
- By last status: `{'ok': 28, 'error': 5}`
- Delivery status counts: `{'delivered': 5, 'not-requested': 6, 'not-delivered': 12, 'unknown': 3}`

## Queue Health

- Status: `pass`
- Queued: `0`
- Pending verification: `0`
- Age buckets: `{'queued': {'state': 'queued', 'count': 0, 'stale_count': 0, 'stale_ratio': 0.0, 'missing_age_or_threshold': 0, 'age_min': None, 'age_max': None, 'age_mean': None, 'age_buckets': {'0-1h': 0, '1-4h': 0, '4-24h': 0, '>24h': 0}}, 'pending_verification': {'state': 'pending_verification', 'count': 0, 'stale_count': 0, 'stale_ratio': 0.0, 'missing_age_or_threshold': 0, 'age_min': None, 'age_max': None, 'age_mean': None, 'age_buckets': {'0-1h': 0, '1-4h': 0, '4-24h': 0, '>24h': 0}}}`
- Assertions: `[]`
- Growth: `{'previous': {'file': 'eval/history/reliability-20260410-141046.json', 'queued': None, 'pending_verification': None}, 'delta': {'queued_delta': 0, 'pending_verification_delta': 0}, 'delta_total_ratio': 0.0, 'slo_pass': True}`

## Delivery Queue

- Files: `0`
- By channel: `{}`
- Top errors: `[]`

## Eval Gate

- Status: `pass`
- Reasons: `[]`

## Queue Snapshot

- Source: `tasks/JOBS/summary.json`
- Counts: `{'queued': 0, 'pending_verification': 0, 'total_jobs': 5, 'workflow_count': 5}`
- Workflow count: `5`