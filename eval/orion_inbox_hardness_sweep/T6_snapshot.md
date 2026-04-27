# Reliability Snapshot

- Generated at: `2026-04-27T14:46:57.227434+00:00`
- Window: last `24h`

## Lane Wait

- Count: `0`
- Max: `0 ms`
- P95: `0 ms`
- By lane: `{}`

## Cron

- Total / Enabled / Disabled: `35 / 1 / 34`
- By agent: `{'unknown': 1}`
- By delivery channel: `{'none': 1}`

## Job State (`jobs-state.json`)

- Version: `1`
- Total: `35`
- By last status: `{'ok': 31, 'error': 2}`
- Delivery status counts: `{'delivered': 5, 'not-delivered': 18, 'not-requested': 2}`

## Queue Health

- Status: `pass`
- Queued: `24`
- Pending verification: `5`
- Age buckets: `{'queued': {'state': 'queued', 'count': 24, 'stale_count': 0, 'stale_ratio': 0.0, 'missing_age_or_threshold': 24, 'age_min': None, 'age_max': None, 'age_mean': None, 'age_buckets': {'0-1h': 0, '1-4h': 0, '4-24h': 0, '>24h': 0}}, 'pending_verification': {'state': 'pending_verification', 'count': 5, 'stale_count': 0, 'stale_ratio': 0.0, 'missing_age_or_threshold': 5, 'age_min': None, 'age_max': None, 'age_mean': None, 'age_buckets': {'0-1h': 0, '1-4h': 0, '4-24h': 0, '>24h': 0}}}`
- Assertions: `[]`
- Growth: `{'previous': {'file': 'eval/history/reliability-20260410-141046.json', 'queued': None, 'pending_verification': None}, 'delta': {'queued_delta': 24, 'pending_verification_delta': 5}, 'delta_total_ratio': 29.0, 'slo_pass': False}`

## Delivery Queue

- Files: `0`
- By channel: `{}`
- Top errors: `[]`

## Eval Gate

- Status: `pass`
- Reasons: `[]`

## Queue Snapshot

- Source: `tasks/JOBS/summary.json`
- Counts: `{'queued': 24, 'pending_verification': 5, 'total_jobs': 29, 'workflow_count': 9}`
- Workflow count: `9`