---
name: task-packet-guard
description: Validate Task Packet formatting in per-agent inbox files to enforce structured delegation.
metadata:
  invocation: user
---

# Task Packet Guard

Validate `TASK_PACKET v1` blocks in `tasks/INBOX/*.md` against `docs/TASK_PACKET.md`.

## Check All Inboxes

```bash
python3 scripts/validate_task_packets.py
```

## Check One Inbox

```bash
python3 scripts/validate_task_packets.py tasks/INBOX/ATLAS.md
```

## What To Do If It Fails

- Fix the packet to include all required fields/sections.
- In specialist inboxes, ensure `Owner:` matches the inbox agent and `Requester:` is `ORION`.
