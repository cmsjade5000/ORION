# ORION Gateway (OpenClaw Workspace)

This repo is an **OpenClaw workspace** for a local-first agent orchestration system ("Gateway").

Design goals:
- single user-facing ingress (ORION)
- specialists are scoped and non-user-facing
- identities are generated to reduce drift
- delegation is structured and auditable (Task Packets)
- secrets never enter Git
- admin-copilot usefulness over dashboards or novelty surfaces

## Runtime Model

- **ORION** (`agentId: main`) is the only user-facing bot (Telegram/Discord/Slack when configured).
- Specialists run as isolated OpenClaw agents: **ATLAS**, **NODE**, **PULSE**, **STRATUS**, **PIXEL**, **QUEST**, **EMBER**, **LEDGER**, **POLARIS**, **SCRIBE**, **WIRE**.
- ORION delegates using `sessions_spawn` (sub-agents) plus a Task Packet (see `docs/TASK_PACKET.md`).
- Specialists return results to ORION only (never message Cory directly).
- ORION local installs should pin `tools.profile` to `coding`; as of OpenClaw `2026.3.x`, new local installs default to `messaging` when unset.

## Go Live (macOS)

Required for reliable heartbeats/cron:

```bash
openclaw config validate --json
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

Latest local runtime verification:
- Upgraded on 2026-03-15 to `OpenClaw 2026.3.13`
- Notes: `docs/OPENCLAW_2026_3_13_UPGRADE_NOTES.md`

## Recovery

Runbook:
- `docs/RECOVERY.md`

## Assistant Focus

Primary assistant posture:
- ORION is a bounded-proactive admin copilot.
- POLARIS is the default internal route for reminders, calendar prep, notes capture, follow-through, and daily review.
- Telegram remains the primary user-facing surface.

Deterministic assistant commands:
- `/today` -> agenda from calendar + reminders + delegated work + open tickets
- `/capture <text>` -> quick admin capture queued to POLARIS
- `/followups` -> waiting-on items and POLARIS queue
- `/review` -> concise daily review / next actions

Generated assistant artifacts:
- `memory/ASSISTANT_PROFILE.md`
- `tasks/NOTES/assistant-agenda.md`
- `tasks/NOTES/error-review.md`
- `tasks/NOTES/session-maintenance.md`

Internal reliability review:
- `python3 scripts/orion_error_db.py review --window-hours 24 --json`
- `AUTO_OK=1 python3 scripts/session_maintenance.py --repo-root . --agent main --fix-missing --apply --doctor --min-missing 50 --min-reclaim 25 --json`
- `docs/ORION_ERROR_REVIEW.md`

## Telegram Mini App (Experimental / Archived)

This repo still contains Mini App experiments, but they are not part of the assistant critical path:
- App: `apps/telegram-miniapp-dashboard/`
- ORION commands: `/miniapp` and `/core` (both send a `web_app` button via the Telegram plugin)
- Paper-trading quick commands in ORION DM:
  - `/paper_help` for a quick in-chat command list
  - `/paper_status` for current paper status
  - `/paper_update` (or `/paper_update 24`) for status + digest window
- Flic conversation commands:
  - `/flic` starts a guided 4-question movie flow and emits a locked Vault picks deep link.
  - `/reroll` keeps the same filters and advances picks offset for a fresh stack.
  - `/flicreset` clears in-memory Flic conversation state for the current DM.

Config:
- Set `ORION_MINIAPP_URL` to your deployed HTTPS URL (see `openclaw.json.example` / `openclaw.yaml`).
- Flic deep-link router env vars:
  - `FLIC_ROUTER_ENABLED=1`
  - `FLIC_VAULT_BASE_URL=https://vault966-r2.fly.dev`
  - `FLIC_BOT_USERNAME=Flic_GatewayBot`
  - Optional: `FLIC_APP_SHORT_NAME=<telegram-miniapp-short-name>`
- Security note: do not enable command routing from the Mini App into ORION unless you explicitly accept the risk (see `SECURITY.md` and the Mini App README).
- Keep the Mini App code for reference and future experiments, but do not treat it as required for assistant behavior.

## Discord (Optional)

OpenClaw includes a bundled Discord channel plugin (disabled by default). This workspace supports Discord as a first-class request + thread routing surface.

Setup:
- `docs/DISCORD_SETUP.md`

## PDF Review Flow

OpenClaw `2026.3.x` introduced first-class PDF analysis plus `sessions_spawn` inline attachments for subagents.

For ORION's preferred workflow, see:
- `docs/PDF_REVIEW_WORKFLOW.md`

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

## CI / Reliability Gate

Local must-pass gate:

```bash
make ci
```

What it checks:
- Python unit tests + Task Packet validation (`npm test`)
- ShellCheck over bash scripts (`scripts/ci_shellcheck.sh`)

Supported validation path:
- Preferred: `npm test`
- TypeScript-only: `npm --prefix app run typecheck`
- Bare `pytest -q` is not the repo default and may use the wrong Python interpreter on macOS.

Opt-in live routing lane:

```bash
make routing-regression-live-dry-run
make routing-regression-live
```

Use this when you want the full local `openclaw agent` routing simulation plus baseline comparison without adding model-dependent runtime to the default CI gate.
