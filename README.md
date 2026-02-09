# ORION Gateway (OpenClaw Workspace)

This repo is an **OpenClaw workspace** for a local-first agent orchestration system ("Gateway").

Design goals:
- single user-facing ingress (ORION)
- specialists are scoped and non-user-facing
- identities are generated to reduce drift
- delegation is structured and auditable (Task Packets)
- secrets never enter Git

## Runtime Model

- **ORION** (`agentId: main`) is the only Telegram-facing bot.
- Specialists run as isolated OpenClaw agents: **ATLAS**, **NODE**, **PULSE**, **STRATUS**, **PIXEL**, **EMBER**, **LEDGER**.
- ORION delegates using `sessions_spawn` (sub-agents) plus a Task Packet (see `docs/TASK_PACKET.md`).
- Specialists return results to ORION only (never message Cory directly).

## Go Live (macOS)

Required for reliable heartbeats/cron:

```bash
openclaw gateway install
openclaw gateway start
openclaw doctor --repair
openclaw security audit --deep
openclaw channels status --probe
```

Verify agents are configured:

```bash
openclaw agents list --bindings
openclaw models status
```

## Recovery

Runbook:
- `docs/RECOVERY.md`

## Workspace Contract (OpenClaw)

OpenClaw injects these workspace files on the first turn of new sessions:
- `AGENTS.md`
- `SOUL.md`
- `TOOLS.md`
- `IDENTITY.md`
- `USER.md`
- `BOOTSTRAP.md` (one-time; delete after go-live)

## Repository Layout

- `src/core/shared/`
  - Shared identity layers included in every generated SOUL.
- `src/agents/`
  - Role definitions (source of truth).
- `scripts/soul_factory.sh`
  - Generates `agents/<AGENT>/SOUL.md`.
- `agents/`
  - Generated SOUL artifacts.
- `docs/TASK_PACKET.md`
  - Delegation spec (cron payloads + ORION -> specialist).
- `tasks/QUEUE.md`
  - Human-readable queue for ORION triage.
- `tasks/INBOX/*.md`
  - Per-agent inboxes for specialist assignments.
- `memory/WORKING.md`
  - Current working state (keep it lean).
- `skills/`
  - Workspace skills (manual installs/updates).

## Regenerating SOULs

```bash
make soul
```

Do not hand-edit `agents/*/SOUL.md`. Change sources in `src/core/shared/` or `src/agents/` and re-run the Soul Factory.

## Secrets

Do not commit secrets. See `KEEP.md`.

OpenClaw runtime config and credentials live under `~/.openclaw/` and must remain local.
