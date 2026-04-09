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
- Checked-in runtime templates now default ORION to `openai/gpt-5.4` with OpenRouter + MiniMax fallbacks.

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

Latest local/runtime baseline:
- Runtime verified on 2026-04-09 against `OpenClaw 2026.4.9`.
- Historical upgrade note remains in `docs/OPENCLAW_2026_3_13_UPGRADE_NOTES.md`.
- Current sweep baseline and follow-on decisions live in:
  - `docs/ORION_RUNTIME_BASELINE_2026_04_07.md`
  - `docs/ORION_TOOL_PILOTS_2026_04.md`
  - `docs/ORION_AGENT_SYSTEM_SWEEP_2026_04_07.md`

Current verification snapshot (2026-04-07):
- `openclaw --version` returned `OpenClaw 2026.4.9`.
- `openclaw config validate --json` returned `{"valid":true,...}`.
- Live runtime plugin allowlist includes `telegram`, `discord`, `slack`, `open-prose`, `minimax`, `google`, `openrouter`, and `openai`.
- Live runtime memory slot is `memory-core`, and dreaming is enabled in runtime.
- ACPX is enabled in the live runtime for bounded specialist execution.
- ACPX live usage is pinned to ATLAS-owned bounded work with `permissionMode=approve-reads`, `nonInteractivePermissions=fail`, and `pluginToolsMcpBridge=false`.
- Firecrawl remains disabled in the live runtime because `FIRECRAWL_API_KEY` is not configured.
- Checked-in templates still keep `memory-lancedb` as the conservative default and keep `memory-core`/dreaming in pilot posture.
- `openclaw skills list` confirms ClawHub-backed skill discovery is available in the local runtime.
- `browser` and `firecrawl` remain bundled plugin surfaces that are not allowlisted in the current live config.
- `make incident-bundle` writes a read-only ORION ops bundle under `tmp/incidents/` plus a stable summary at `tasks/NOTES/orion-ops-status.md`.

Capability intake brief:
- `docs/ORION_RUNTIME_BASELINE_2026_04_07.md`
- `docs/ORION_TOOL_PILOTS_2026_04.md`
- `docs/ORION_AGENT_SYSTEM_SWEEP_2026_04_07.md`
- Historical context:
  - `docs/OPENCLAW_CAPABILITY_INTAKE_2026_03_18.md`
  - `docs/ORION_TOOLSET_ADOPTION_2026_03_22.md`
- `docs/ORION_FUNCTIONAL_REVIEW_2026_04_06.md`
- `docs/OPENCLAW_MEMORY_DREAMING_PILOT.md`

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
- `python3 scripts/orion_incident_bundle.py --repo-root . --write-latest --json`
- `docs/ORION_ERROR_REVIEW.md`

Memory/dreaming pilot:
- ORION keeps `MEMORY.md` as curated truth and `memory-lancedb` as the active checked-in template default for now.
- Live runtime has moved to `memory-core` with dreaming enabled; treat that as runtime state, not a blanket repo default.
- OpenClaw `2026.4.9` dreaming remains documented here as a pilot path under `memory-core`, not an auto-trusted memory source.
- See `docs/OPENCLAW_MEMORY_DREAMING_PILOT.md` before switching the memory slot or enabling `/dreaming`.
- For dreaming to populate short-term recall, ORION memory search must include `memory` in `agents.list[].memorySearch.sources`; `sessions` alone will not write the dreaming recall store.
- For deterministic direct ORION turns, prefer the guarded wrapper path over raw `openclaw agent`:
  - `make dreaming-status`
  - `make dreaming-help`
  - `make dreaming-on`
  - `make dreaming-off`
- Non-destructive preview:
  - `make dreaming-preview`
  - writes `tmp/openclaw_memory_dreaming_preview_latest.json`
  - writes `tmp/openclaw_memory_dreaming_preview_latest.md`
  - reports whether a local short-term recall store exists yet

Standard operator health bundle:
- Run `make operator-health-bundle` after gateway, model, or memory changes.
- It checks gateway status, `models status --probe`, memory status, `memory rem-harness`, and one live `main` smoke turn.
- Artifacts:
  - `tmp/openclaw_operator_health_bundle_latest.json`
  - `tmp/openclaw_operator_health_bundle_latest.md`

## Telegram Surfaces

Primary Telegram commands in ORION DM:
- Paper-trading quick commands:
  - `/paper_help` for a quick in-chat command list
  - `/paper_status` for current paper status
  - `/paper_update` (or `/paper_update 24`) for status + digest window
- Flic conversation commands:
  - `/flic` starts a guided 4-question movie flow and emits a locked Vault picks deep link.
  - `/reroll` keeps the same filters and advances picks offset for a fresh stack.
  - `/flicreset` clears in-memory Flic conversation state for the current DM.

Config:
- Flic deep-link router env vars:
  - `FLIC_ROUTER_ENABLED=1`
  - `FLIC_VAULT_BASE_URL=https://vault966-r2.fly.dev`
  - `FLIC_BOT_USERNAME=Flic_GatewayBot`
  - Optional: `FLIC_APP_SHORT_NAME=<telegram-miniapp-short-name>`

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

## Skill Ownership

- The current per-agent skill and tool ownership matrix lives in `docs/ASSISTANT_SKILLS.md`.
- Use ClawHub as the standard discovery/update channel for skill review, but keep repo curation and policy review in the loop.
- Treat setup-gated skills as `pending setup`, not live capability.

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
- Promptfoo config validation and optional redteam gate:
  - `docs/PROMPTFOO_GATE.md`

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
