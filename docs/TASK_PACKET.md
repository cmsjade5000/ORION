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
Requester: ORION
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

## Validation (Recommended)

Validate inbox packets stay structured:

```bash
python3 scripts/validate_task_packets.py
```
