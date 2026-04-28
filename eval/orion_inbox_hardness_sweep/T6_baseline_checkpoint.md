# ORION Inbox Queue Hardness Sweep — T6 Baseline Checkpoint

Date: 2026-04-27  
Phase: `T6: Hardness Snapshot & SLO Gate`  
Operator scope: Telegram-only queue lifecycle hardening

## Checkpoint
- Baseline file: `eval/history/reliability-20260427-154642.json`
- Checkpoint artifact set:
  - `eval/orion_inbox_hardness_sweep/T6_final_gate_snapshot.json`
  - `eval/orion_inbox_hardness_sweep/T6_final_gate_snapshot.md`
  - `eval/orion_inbox_hardness_sweep/T6_hardness_gate_report.md`

## Commands run for freeze
1. `python3 scripts/collect_reliability_snapshot.py --hours 24`
2. `python3 scripts/collect_reliability_snapshot.py --hours 24 --output-json eval/orion_inbox_hardness_sweep/T6_final_gate_snapshot.json --output-md eval/orion_inbox_hardness_sweep/T6_final_gate_snapshot.md`

## Baseline pass criteria (frozen state)
- `queue_queued: 0`
- `queue_pending_verification: 0`
- `queue_health: pass`
- `queue_growth.slo_pass: true`
- `slo_status: pass`
- `eval_gate: pass`

## Next precondition
- Next T6 run should use this baseline (`.../reliability-20260427-154642.json`) as the previous artifact for growth comparisons until a larger queue-expanding run changes the normal operating point.
- If a major queue-expanding operator batch happens, rerun:
  - `python3 scripts/task_execution_loop.py --repo-root . --apply --stale-hours 24 --state-path tmp/task_execution_loop_state.json`
  - `python3 scripts/collect_reliability_snapshot.py --hours 24 --output-json eval/orion_inbox_hardness_sweep/T6_final_gate_snapshot.json --output-md eval/orion_inbox_hardness_sweep/T6_final_gate_snapshot.md`
