# Memory (Curated, Long-Term)

This file is for **stable, high-signal notes** that should persist across sessions.

Rules:
- Keep it short and curated. No logs.
- Do not store secrets or tokens here (see `KEEP.md`).
- Prefer writing transient state to `memory/WORKING.md` and tasks to `tasks/`.

## Communication Constraint (Current)

- ORION is the only agent that communicates with Cory via Telegram.
- Specialists (ATLAS, NODE, etc.) are internal-only and return results to ORION.

## Where To Put Things

- `memory/WORKING.md`
  - Current goal, blockers, "what is happening right now".
- `tasks/QUEUE.md`
  - Active queue ORION can triage.
- `tasks/INBOX/<AGENT>.md`
  - ORION assigns specialist work as Task Packets.

## What Must Never Go In Git

- API keys, bot tokens, OAuth caches, auth profiles.
- Anything under `~/.openclaw/`.
