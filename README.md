# ORION Core Gateway (OpenClaw Workspace)

This repo is an **OpenClaw workspace** for ORION core: a local-first admin copilot and safe orchestration system.

Design goals:
- single user-facing ingress (ORION)
- a small default specialist surface for core work
- identities are generated to reduce drift
- delegation is structured and auditable (Task Packets)
- secrets never enter Git
- admin-copilot usefulness over novelty surfaces or product sprawl

## Start Here

If you are new to the repo, start with [docs/ORION_START_HERE.md](/Users/corystoner/src/ORION/docs/ORION_START_HERE.md).

## Runtime Model

- **ORION** (`agentId: main`) is the only user-facing bot (Telegram/Discord/Slack when configured).
- Default ORION core delegation lanes are **ATLAS**, **POLARIS**, **WIRE**, and **SCRIBE**.
- Optional retained lanes are **LEDGER** and **EMBER**.
- **NODE**, **PULSE**, and **STRATUS** remain internal implementation detail behind **ATLAS**.
- **PIXEL** and **QUEST** remain available only as non-core extension lanes and are not part of the default ORION core routing surface.
- ORION delegates using `sessions_spawn` plus a Task Packet, and uses `sessions_yield` for active long-running sessions while keeping Task Packets as the durable record (see `docs/TASK_PACKET.md` and `docs/NATIVE_SUBAGENT_CONTROL_PLANE.md`).
- Specialists return results to ORION only (never message Cory directly).
- ORION local installs should pin `tools.profile` to `coding`; as of OpenClaw `2026.3.x`, new local installs default to `messaging` when unset.
- Checked-in runtime templates now default ORION to `openrouter/openrouter/free` with cheap/free fallbacks first; premium OpenAI/Codex lanes are explicit opt-in only.

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
- Runtime verified on 2026-04-29 against `OpenClaw 2026.4.27`.
- Historical upgrade note remains in `docs/OPENCLAW_2026_3_13_UPGRADE_NOTES.md`.
- Current sweep baseline and follow-on decisions live in:
  - `docs/ORION_RUNTIME_BASELINE_2026_04_07.md`
  - `docs/ORION_TOOL_PILOTS_2026_04.md`
  - `docs/ORION_AGENT_SYSTEM_SWEEP_2026_04_07.md`

Current verification snapshot (2026-04-29):
- `openclaw --version` returned `OpenClaw 2026.4.27`.
- `openclaw config validate --json` returned `{"valid":true,...}`.
- `openclaw gateway status --json` returned a healthy loopback LaunchAgent and `openclaw gateway call status --json` reported the current `2026.4.x` runtime.
- Live runtime plugin entries include `acpx`, `bluebubbles`, `discord`, `memory-core`, `minimax`, `open-prose`, `openai`, `openrouter`, `slack`, and `telegram`.
- Live runtime memory slot is `memory-core`, and dreaming is enabled in runtime.
- ACPX is enabled in the live runtime for bounded specialist execution.
- ACPX live usage is pinned to ATLAS-owned bounded work with `permissionMode=approve-reads`, `nonInteractivePermissions=fail`, and `pluginToolsMcpBridge=false`.
- Firecrawl remains disabled in the live runtime because `FIRECRAWL_API_KEY` is not configured.
- Checked-in templates still keep `memory-lancedb` as the conservative default while the live runtime uses `memory-core` with dreaming enabled.
- OpenClaw `2026.4.20` and `2026.4.21` added stricter owner-command auth, startup/health-reporting improvements, session pruning by default, cron runtime-state splitting (`jobs-state.json` beside `jobs.json`), and better doctor/plugin dependency repair paths.
- OpenClaw `2026.4.27` adds ORION-relevant Telegram startup/send/topic-cron fixes, plugin registry/startup hygiene, strict model fallback behavior, and `models.pricing.enabled` for low-cost/offline startup.
- Deferred `2026.4.27` surfaces: DeepInfra, Yuanbao, QQBot, Matrix, Slack, Docker GPU passthrough, and mobile node presence.
- The older `OPENCLAW_GATEWAY_TOKEN` LaunchAgent audit warning from `2026.4.14` is not the current verified state on this machine; the current LaunchAgent config audit is clean, but still verify after reinstalls.
- The bundled Discord runtime dependency stack required a local npm rebuild after the `2026.4.21` upgrade; gateway and Telegram recovered cleanly afterward.
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
- `docs/OPENCLAW_MEMORY_DREAMING.md`

## Recovery

Runbook:
- `docs/RECOVERY.md`

## Assistant Focus

Primary assistant posture:
- ORION is a bounded-proactive admin copilot.
- POLARIS is the default internal route for reminders, calendar prep, notes capture, follow-through, and daily review.
- Telegram remains the primary user-facing surface.
- Primeta is available as an optional avatar/presentation layer via MCP; it does not replace ORION's routing, Task Packets, or Telegram/TTS defaults.

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

Memory/dreaming:
- ORION keeps `memory-lancedb` as the active checked-in template default for now.
- Live runtime has moved to `memory-core` with dreaming enabled; treat that as runtime state, not a blanket repo default.
- OpenClaw `2026.4.14` is the current verified runtime; dreaming remains documented here as the active `memory-core` path.
- See `docs/OPENCLAW_MEMORY_DREAMING.md` before switching the memory slot or enabling `/dreaming`.
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
- By default it stays read-only: gateway status, `models status`, memory status, and `memory rem-harness`.
- Live token spend is opt-in via `ALLOW_LIVE_MODEL_PROBE=1` and/or `ALLOW_LIVE_SMOKE=1`.
- Repo planning and code-mod work should stay in low-cost mode by default; see `docs/LOW_COST_MODE.md`.
- Artifacts:
  - `tmp/openclaw_operator_health_bundle_latest.json`
  - `tmp/openclaw_operator_health_bundle_latest.md`

## Core Boundary

ORION core owns:
- admin-copilot Telegram commands (`/today`, `/capture`, `/followups`, `/review`)
- the private ORION Telegram Main Mini App (`/orion`)
- task packets, delegated-job state, and core maintenance loops
- routing, retrieval, drafting, safety, and proof-driven execution

ORION core does not own by default:
- trading, market, game, or media product surfaces
- product-specific Telegram commands
- product-specific scheduled jobs

Non-core surfaces now live behind explicit extension seams. See:
- `docs/ORION_SINGLE_BOT_ORCHESTRATION.md`
- `docs/ORION_EXTENSION_SURFACES.md`
- `apps/extensions/`

## Telegram Surfaces

Primary Telegram commands in ORION DM:
- `/today` for agenda from calendar + reminders + delegated work + open tickets
- `/capture <text>` for quick capture queued to POLARIS
- `/followups` for waiting-on items and POLARIS queue
- `/review` for concise daily review / next actions
- `/orion` for the private Telegram Main Mini App
- `/agents` for the core agent dashboard
- `/dreaming ...` for guarded memory/dreaming controls

Mini App docs:
- `docs/ORION_TELEGRAM_MINI_APP.md`

## Optional Avatar Layer

Primeta can sit on top of ORION as an opt-in avatar layer for spoken summaries and animated reactions.

- Keep it presentation-only.
- Do not treat it as a new user-facing ingress.
- Do not make normal ORION delivery depend on Primeta availability or OAuth state.

Operator docs:
- `docs/PRIMETA_AVATAR_LAYER.md`
- `scripts/primeta_avatar.py`

## Discord (Optional)

OpenClaw includes a bundled Discord channel plugin (disabled by default). ORION core keeps Discord available as an optional request/update surface, but not as a reason to widen the default specialist or product surface.

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
- `docs/ORION_EXTENSION_SURFACES.md`
  - Boundary and handoff model for non-core product surfaces.
- `docs/REPO_HYGIENE.md`
  - What stays versioned versus what should remain local runtime state.
- `apps/extensions/`
  - Moved extension-owned Telegram/product surfaces that are not part of the default ORION core runtime path.
- `memory/WORKING.md`
  - Current working state (keep it lean).
- `skills/`
  - Workspace skills (manual installs/updates).

## Skill Ownership

- The current per-agent skill and tool ownership matrix lives in `docs/ASSISTANT_SKILLS.md`.
- Repo-wide cost policy and low-spend defaults live in `docs/LOW_COST_MODE.md`.
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
