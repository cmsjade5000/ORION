# Delegated Jobs

This directory contains derived per-job state for Task Packet work.

- Source inputs: `tasks/INBOX/*.md`, ticket lanes, and task-loop pending state.
- Writer: `python3 scripts/task_execution_loop.py --apply` or `python3 scripts/inbox_cycle.py`.
- Files:
  - `pkt-*.json` / `ik-*.json`: one durable delegated-job record per active packet
  - `summary.json`: current aggregate snapshot

These files are derived artifacts. The source of truth remains the inbox packet and any linked ticket.
