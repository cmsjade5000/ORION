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
- Ensure `Owner:` matches the inbox agent.
- Ensure `Requester:` follows chain-of-command:
- For `tasks/INBOX/NODE.md`, `tasks/INBOX/PULSE.md`, `tasks/INBOX/STRATUS.md`: `Requester: ATLAS` (or `Requester: ORION` only with `Emergency: ATLAS_UNAVAILABLE`).
- For other specialist inboxes: `Requester: ORION`.
