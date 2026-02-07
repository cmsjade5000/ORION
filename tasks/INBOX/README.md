# Per-Agent Inboxes

These files are lightweight assignment queues for specialists.

## How It Works

- ORION assigns work by appending a `TASK_PACKET v1` block to `tasks/INBOX/<AGENT>.md`.
- Specialists pick up work from their inbox and write back a `Result:` section under the packet.
- If a task is too large, the specialist should propose a split and ask ORION to re-issue as multiple packets.

## Task Packet Spec

See `docs/TASK_PACKET.md`.
