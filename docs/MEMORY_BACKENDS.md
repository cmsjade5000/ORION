# Memory Backends

Gateway is file-backed and local-first.

Current stance:
- Use `memory/WORKING.md` for active state.
- Use `tasks/` for queues and delegation artifacts.
- Keep `MEMORY.md` as a curated long-term memory file (short, stable, no logs).

Notes:
- OpenClaw treats the workspace as the agent's home. Keep it private and free of secrets (see `KEEP.md`).
