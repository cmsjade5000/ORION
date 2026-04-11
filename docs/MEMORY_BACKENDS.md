# Memory Backends

Gateway is file-backed and local-first.

Current stance:
- Use `memory/WORKING.md` for active state.
- Use `tasks/` for queues and delegation artifacts.
- Keep `MEMORY.md` as a curated long-term memory file (short, stable, no logs).

Notes:
- OpenClaw treats the workspace as the agent's home. Keep it private and free of secrets (see `KEEP.md`).

## ORION Dreaming Path

OpenClaw `2026.4.10` exposes dreaming in `memory-core`.

ORION stance:
- Keep `memory-lancedb` as the active template default until memory reliability is boring.
- Treat dreaming as an active background memory process under `memory-core`.
- Keep `MEMORY.md` as the compact durable memory file for intentionally maintained notes.
- Treat `DREAMS.md` as a review surface generated from dreaming output.

Official surface:
- Config key: `plugins.entries.memory-core.config.dreaming`
- Minimal enablement: `enabled: true`
- Optional schedule override: `frequency`
- Chat control: `/dreaming on|off|status|help`
- Review CLI:
  - `openclaw memory status --deep`
  - `openclaw memory promote`
  - `openclaw memory promote --apply`
  - `openclaw memory promote-explain "<selector>"`
  - `openclaw memory rem-harness --json`

See:
- [OPENCLAW_MEMORY_DREAMING.md](/Users/corystoner/src/ORION/docs/OPENCLAW_MEMORY_DREAMING.md)
