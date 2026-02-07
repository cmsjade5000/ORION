# Task Queue

This file is ORION’s human-readable triage list.

For specialist work, prefer per-agent inboxes under `tasks/INBOX/` using a Task Packet (`docs/TASK_PACKET.md`).

## Ready (ORION triage)
- [ ] (add task)

## Specialist Assignments (ORION-only)

If a task should be executed by a specialist, ORION assigns it as a **Task Packet** to:

- `tasks/INBOX/<AGENT>.md`

See `docs/TASK_PACKET.md`.

## In Progress

## Blocked

## Done Today

### Rules
- ORION chooses the next item and either executes it or assigns it via a Task Packet.
- Specialists should not self-pick tasks from this file unless explicitly assigned.
- Do not put secrets or personal tokens here.
