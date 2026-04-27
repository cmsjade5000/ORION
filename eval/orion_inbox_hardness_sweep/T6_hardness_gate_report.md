# ORION Inbox Queue Hardness Sweep — T6 Gate Report

Date: 2026-04-27  
Phase: `T6: Hardness Snapshot & SLO Gate`  
Mode: Telegram-only queue lifecycle scope, one-pass migration posture

## 1) T5 Upgrade/Tool Utilization Summary (Local + OpenClaw drift matrix)

- Source evidence:
  - `eval/orion_inbox_hardness_sweep/T5_upgrade_matrix.md`
  - `eval/orion_inbox_hardness_sweep/T5_owner_command_auth_check.txt`
- Status rollup:
  - `pass`: jobs/jobs-state split (`jobs.json` + `jobs-state.json`), duplicate cron overlap guard cleanup, notifier failure contract (`delivered/suppressed/failed-to-deliver` + dead-letter), plugin registry health, queue-state invariants, Codex routing posture.
  - `warn`: owner-command auth hardening (`commands.ownerAllowFrom` is absent in baseline; write path verified, but no hard allow/deny proof yet).
  - `warn`: session pruning stress test not covered in this pass.
- Remediation owners:
  - Owner commands: `ORION`
  - Session pruning/checks: `ORION`

## 2) T6 SLO Gate Inputs (Latest evidence)

- Snapshot artifact: `eval/orion_inbox_hardness_sweep/T6_final_gate_snapshot.json`
- Generated: `2026-04-27T15:46:44.401300+00:00`
- Window: `24h`

### Queue contract
- Canonical queue contract (`tasks/JOBS/summary.json` + cron surface): `pass`
- Canonical launcher session target: `launchagent` (present and enabled)
- Legacy queue cron jobs enabled: `[]`
- Queue artifacts reflected in durable summary (`tasks/JOBS/summary.json`) only.

### Queue health counters
- `queued`: `0` (threshold `<= 160` => pass)
- `pending_verification`: `0` (threshold `<= 120` => pass)
- `pending_verification` ratio share: `0.0000` (threshold `<= 0.60` => pass)
- Stale ratio (all states): `0.0` (threshold `<= 0.20` => pass)

### Queue growth
- `queued_delta`: `0`
- `pending_verification_delta`: `0`
- `delta_total_ratio`: `0.0`
- Growth SLO check uses `abs(delta_ratio) <= 0.40` => **pass** (`abs(0.0) = 0.0`)

### Jobs state + delivery
- `jobs-state total`: `34`
- `by last status`: `{'ok': 30, 'error': 2}`
- `delivery status`: `{'delivered': 5, 'not-delivered': 17, 'not-requested': 2}`
- Eval gate (from `eval/latest_compare.json`): `pass`

### Notifier + cron
- Delivery queue files: `0`
- Cron enabled: `1 / 34`
- Queue contract status: `pass` (by script contract rules)

## 3) Gate Decision (T6)

- **Overall T6 status: `PASS`**
- Blocking reasons:
  None
- Observed:
  1. Notification pipeline and job-state surfaces are healthy and coherent after recent cleanup.
  2. No stale ratio violations.
  3. Cron contract remains clean for queue migration scope.

## 4) Precondition for next batch (operator gate)

- Do not open non-`T` queue-expanding run batches while either condition is unresolved:
  - none currently.
- With `T6` passing, continue normal operator flow and rerun this gate before the next major queue-expanding batch.
  - `python3 scripts/collect_reliability_snapshot.py --output-json eval/orion_inbox_hardness_sweep/T6_final_gate_snapshot.json --output-md eval/orion_inbox_hardness_sweep/T6_final_gate_snapshot.md`
  - and regenerate this gate artifact before next operator changes.
