# OpenClaw Gateway Task Queue Testing

The local ORION queue path is packet-backed:

1. A user-facing ORION request is represented as a `TASK_PACKET v1` entry in `tasks/INBOX/<OWNER>.md`.
2. `scripts/run_inbox_packets.py` claims safe, allowlisted, read-only packets and writes a `Result:` block plus an artifact log.
3. `scripts/task_execution_loop.py --apply` reconciles packet state, handles stale/recovery handoffs, and writes `tasks/JOBS/<job>.json`, `tasks/JOBS/wf-*.json`, and `tasks/JOBS/summary.json`.
4. `scripts/inbox_cycle.py` is the production wrapper: runner, email reply worker, reconcile, notify, archive, doctor.

For repeatable regression tests, realistic prompts live in `tests/fixtures/orion_realistic_user_prompts.jsonl`. The local harness in `scripts/orion_realistic_prompt_queue_harness.py` converts each prompt into a safe staging Task Packet, preserves the original wording in the packet inputs, runs the real inbox runner and reconcile path, and verifies job artifacts.

The harness never contacts providers, Telegram, AgentMail, or production queues. It creates an isolated temp repo, uses a local allowlisted command stub, and sets `ORION_TASK_LOOP_SKIP_OPENCLAW_SNAPSHOT=1` so queue lifecycle tests are not blocked by live gateway availability.

Run the focused suite with:

```bash
python3 -m unittest tests.test_orion_realistic_prompt_queue_harness tests.test_run_inbox_packets_retry tests.test_task_execution_loop
```

Run all Python queue checks with:

```bash
npm run test:py
```
