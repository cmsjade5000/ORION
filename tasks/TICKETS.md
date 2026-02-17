# Tickets

This is the repo-native, file-first ticket workflow used by ORION.

## Folder Lanes

- `tasks/WORK/backlog/` queued tickets (filename ordering is the queue)
- `tasks/WORK/in-progress/` tickets currently being executed
- `tasks/WORK/testing/` tickets awaiting verification
- `tasks/WORK/done/` completed tickets
- `tasks/WORK/assignments/` lightweight assignment breadcrumbs (optional)
- `tasks/WORK/artifacts/` per-ticket deliverables (logs, diffs, screenshots, reports)

Raw incoming requests live in:
- `tasks/INTAKE/` (append-only)

Specialist assignment queues live in:
- `tasks/INBOX/*.md` (Task Packets)

## Ticket Naming

Tickets are numbered:
- `0001-<slug>.md`, `0002-<slug>.md`, ...

The lowest number in `tasks/WORK/backlog/` is “next up” unless explicitly blocked.

## Ticket Format (Required)

```md
# 0001-short-title

Owner: ORION|ATLAS|NODE|PULSE|STRATUS|WIRE|PIXEL|LEDGER|EMBER|SCRIBE
Status: queued|in-progress|testing|done|blocked

## Context
Why this exists. Links to intake items, PRs, incidents, etc.

## Requirements
- ...

## Acceptance Criteria
- ...

## Artifacts
- tasks/WORK/artifacts/0001-short-title/...

## Notes
- Dated updates go here.
```

## Integration With Task Packets (Specialists)

When work should be executed by a specialist:

1. Create/ensure a ticket exists in `tasks/WORK/backlog/`.
2. ORION appends a `TASK_PACKET v1` to `tasks/INBOX/<AGENT>.md` that references the ticket path.
3. The specialist writes progress back into the ticket (and/or adds artifacts under `tasks/WORK/artifacts/<ticket>/`)
   and adds a `Result:` section under the Task Packet.

Rule of thumb:
- Tickets are the durable “what/why/done”.
- Task Packets are the “who/execute/return results”.

## Helper CLI (Optional)

This repo includes a small helper script:

- Create ticket: `python3 scripts/tickets.py new --title "..." --intake tasks/INTAKE/...`
- Move ticket: `python3 scripts/tickets.py move --ticket 12 --to in-progress --note "started work"`
