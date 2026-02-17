# Task Packet Spec

This document defines the canonical **Task Packet** format used for:

- Cron payloads (OpenClaw `agentTurn` messages)
- ORION → specialist delegation (sessions/swarm)
- ORION → per-agent inbox assignment (`tasks/INBOX/*.md`)

Goal: keep delegation structured, auditable, and low-ambiguity.

## Rules

- ORION must include a Task Packet for any non-trivial delegation.
- Cron jobs must use a Task Packet in the `--message` payload.
- Specialists should refuse work that lacks enough fields to execute safely.

## Minimal Task Packet (Required Fields)

Use this exact header + list format:

```text
TASK_PACKET v1
Owner: <AGENT>          # who executes (ATLAS/NODE/etc)
Requester: <ORION|ATLAS>
Objective: <one sentence outcome>
Success Criteria:
- <verifiable check 1>
Constraints:
- <must/never rules>
Inputs:
- <paths/links/snippets>
Risks:
- <risk + mitigation or "low">
Stop Gates:
- <what requires Cory approval>
Output Format:
- <diff/checklist/report/commands>
```

## Optional Fields (Use When Helpful)

- `Context:` short background paragraph
- `Scope:` included/excluded
- `Timebox:` e.g., `30m` or `2h`
- `Dependencies:` other tasks/agents needed first
- `Checkpoints:` interim status points
- `Notify:` `telegram` | `discord` | `none` (also supports `telegram,discord`)
  - Use `Notify: telegram` when a delegated packet is user-initiated and Cory expects a follow-up message when the specialist posts a `Result:`.
  - If the packet will execute via the inbox runner, use `Notify: telegram` so Cory gets:
    - a one-time "Queued" update, and
    - a follow-up "Results" update when `Result:` is written.
- `Idempotency Key:` optional stable key to dedupe runner-backed packets across retries/reruns.
  - Used by `scripts/run_inbox_packets.py` to avoid repeating the same work when the packet is re-filed or re-queued.
- Retry policy (used by `scripts/run_inbox_packets.py` for allowlisted read-only packets):
  - `Retry Max Attempts:` integer (default `1`, meaning no retries)
  - `Retry Backoff Seconds:` number (default `60`)
  - `Retry Backoff Multiplier:` number (default `2`)
  - `Retry Max Backoff Seconds:` number (default `3600`)
- `Severity:` `P0` (emergency) | `P1` (urgent) | `P2` (normal) | `P3` (backlog)
- `Emergency:` use only for explicit emergency modes (example: `ATLAS_UNAVAILABLE`)
- `Incident:` incident id when an emergency bypass is used (see `tasks/INCIDENTS.md`)

## Cron Payload Guidance

Cron jobs are blind execution. Keep cron packets:

- bounded (timebox + narrow scope)
- non-destructive by default
- `deliver=false` unless Cory explicitly wants messages

Example cron `--message` payload (inline):

```text
TASK_PACKET v1
Owner: ORION
Requester: ORION
Objective: Run heartbeat once and update tasks/QUEUE.md if needed.
Success Criteria:
- Returns HEARTBEAT_OK when idle.
- Updates tasks/QUEUE.md only when there is a clear Ready item.
Constraints:
- Do not browse endlessly.
- Do not message Telegram unless explicitly asked in the task.
Inputs:
- HEARTBEAT.md
- tasks/QUEUE.md
Risks:
- low
Stop Gates:
- Any destructive command.
- Any credential change.
Output Format:
- Short checklist of what was checked + what changed.
```

## ORION → Specialist Session Guidance

For internal sessions, include:

- Specialist SOUL: `agents/<AGENT>/SOUL.md`
- Policy anchors: `SECURITY.md`, `TOOLS.md`, `USER.md`
- Task Packet (in-message or as a file link)

## Per-Agent Inbox Guidance

Inbox files are append-only queues of Task Packets.

- ORION assigns by appending a new Task Packet to `tasks/INBOX/<AGENT>.md`.
- Specialist marks completion by adding a short `Result:` block under the packet.
- Do not pre-create an empty `Result:` placeholder. Leave the `Result:` block for the specialist/runner.
- If the packet included `Notify: telegram`, ORION may notify Cory automatically (see `scripts/notify_inbox_results.py` + `HEARTBEAT.md`).
- For allowlisted read-only packets, `scripts/run_inbox_packets.py` can execute the `Commands to run:` section and write the `Result:` block.
  - Formatting requirement for `Commands to run:`:
    - Preferred: header line `Commands to run:` followed by bullet lines (example `- diagnose_gateway.sh`).
    - Supported: single-line form `Commands to run: diagnose_gateway.sh`.
- Requester field policy:
  - Most specialist inboxes: `Requester: ORION`.
  - ATLAS-directed sub-agents (`NODE`, `PULSE`, `STRATUS`): `Requester: ATLAS` (or `Requester: ORION` only with `Emergency: ATLAS_UNAVAILABLE`).

## Validation (Recommended)

Validate inbox packets stay structured:

```bash
python3 scripts/validate_task_packets.py
```
