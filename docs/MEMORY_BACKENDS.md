# Memory Backends

Gateway is file-backed and local-first.

Current stance:
- Use `memory/WORKING.md` for active state.
- Use `tasks/` for queues and delegation artifacts.
- Keep `MEMORY.md` as a curated long-term memory file (short, stable, no logs).

Notes:
- OpenClaw treats the workspace as the agent's home. Keep it private and free of secrets (see `KEEP.md`).

## ORION Pilot Path: Dreaming

OpenClaw `2026.4.5` adds an experimental dreaming system in `memory-core`.

ORION stance:
- Keep `memory-lancedb` as the active template default until memory reliability is boring.
- Treat dreaming as a pilot path, not part of the assistant critical path.
- Keep `MEMORY.md` as curated truth even when dreaming is enabled.
- Treat `DREAMS.md` as a review surface, not an auto-trusted fact store.

Official pilot surface:
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
- [OPENCLAW_MEMORY_DREAMING_PILOT.md](/Users/corystoner/Desktop/ORION/docs/OPENCLAW_MEMORY_DREAMING_PILOT.md)
