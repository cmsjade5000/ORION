# T3 Synthetic Lifecycle Evidence (Post-Cleanup)

## Artifact Inputs
- Inbox packet file: `tasks/INBOX/hardness_sweep_sandbox.md`
- Inbox packet artifact: `tasks/JOBS/pkt-8ba4d69160559054.json`
- Summary source: `tasks/JOBS/summary.json`
- Sweep script evidence: `scripts/inbox_cycle.py`

## Lifecycle Trace (Canonical Surface)
1) Queue input created
- Added a `TASK_PACKET v1` for a synthetic packet with objective: `Synthetic lifecycle sweep for ORION queue migration (post-cleanup).`
- Packet `Notify:` remains `telegram`.

2) Queue transition
- `task_execution_loop` path in `scripts/inbox_cycle.py` processed the packet from inbox into durable job artifact.
- Captured job artifact: `tasks/JOBS/pkt-8ba4d69160559054.json`
- Initial durable state observed before result append:
  - `state`: `queued`
  - `state_reason`: `pending_packet`
  - `result.present`: `false`

3) Result transition
- Appended `Result:` block to the same inbox packet (`Status: OK`).
- Re-ran `scripts/inbox_cycle.py --repo-root .` with telegram/discord suppression.
- Job artifact updated to:
  - `state`: `pending_verification`
  - `state_reason`: `result_ok_waiting_done`
  - `result.present`: `true`
  - `result.raw_status`: `OK`

4) Canonical-state verification
- Summary entry includes synthetic job:
  - `job_id`: `pkt-8ba4d69160559054`
  - `state`: `pending_verification`
  - `queued_digest`: `8ba4d69160559054b19c1ef1977a7b8224307eab946bab74b727dcae041461fb`
  - `result_digest`: `fc76a4572f8206042d389168939dc2c0741e5ab9298e833161a3ade95c425079`
  - `inbox.path`: `tasks/INBOX/hardness_sweep_sandbox.md`
  - `inbox.line`: `19`

5) Summary integrity
- `tasks/JOBS/summary.json` contains `counts` and canonical job list; queue view reads this file and no fallback to inbox markdown for state inference.
