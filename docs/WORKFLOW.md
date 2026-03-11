# Developer Workflow

This document outlines the recommended workflow for developing and maintaining the Gateway system.

## Setup

1. **Prerequisites**
   - Git (>=2.x)
   - Bash (>=4.x)
   - OpenClaw CLI (`openclaw`) and daemon
   - `pre-commit` (optional, for linting and formatting)
2. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd ORION
   ```
3. **Install pre-commit hooks**
   ```bash
   pip install pre-commit   # or use your system package manager
   pre-commit install
   ```
4. **Regenerate agent identities**
   ```bash
   make soul
   ```
5. **Configure integrations**
   - Create a Telegram token file at `~/.openclaw/secrets/telegram.token` (plain token value).
   - The active OpenClaw config is `~/.openclaw/openclaw.json`. Use it for runtime settings.
   - Keep `openclaw.yaml` in this repo as a project reference template.
   - For model provider setup (where to get keys + how to wire them into OpenClaw), see `docs/LLM_ACCESS.md`.
   - See `docs/OPENCLAW_CONFIG_MIGRATION.md` for mapping details.
   - For single-bot delegation behavior, follow `docs/ORION_SINGLE_BOT_ORCHESTRATION.md`.
   - For delegation structure, follow `docs/TASK_PACKET.md` and `tasks/INBOX/`.
   - For Discord setup and ongoing practice/evaluation, follow `docs/DISCORD_SETUP.md` and `docs/DISCORD_TRAINING_LOOP.md`.
   - Optional Mini App dashboard:
     - Set `ORION_MINIAPP_URL` (deployed HTTPS URL). ORION exposes `/miniapp`.
     - See `apps/telegram-miniapp-dashboard/README.md` for deployment + security notes.
   - For best gateway-service reliability, store model/provider auth using `openclaw models auth paste-token` (LaunchAgent services may not inherit your shell env vars).
   - For email, follow `docs/EMAIL_POLICY.md` (ORION-only inbox; threat preflight; draft-first outbound).
   - For structured administrative intelligence (reports, comparisons, triage, dashboards), follow `docs/ADMIN_INTELLIGENCE_PLAYBOOK.md`.
   - For outages/power failures/manual restart, follow `docs/RECOVERY.md` (and use `./status.sh` for a fast local+AEGIS snapshot).

6. **Go live locally (recommended order)**
   ```bash
   openclaw config validate --json
    openclaw gateway install
   openclaw gateway start
   openclaw doctor --repair
   openclaw security audit --deep
   openclaw channels status --probe
   openclaw agents list --bindings
   ```
   - As of OpenClaw `2026.3.x`, new local installs default to `tools.profile=messaging` when unset.
   - ORION should pin `tools.profile` to `coding` in local installs.

## Daily Commands

Use the top-level Makefile aliases to streamline common tasks:

| Command             | Description                                        |
|---------------------|----------------------------------------------------|
| `make dev`          | Start or resume the OpenClaw gateway service.      |
| `make restart`      | Restart the OpenClaw gateway service.              |
| `make soul`         | Regenerate all agent `SOUL.md` identity files.     |
| `make routingsim`   | Run routing eval + regression gate against baseline. |
| `make routing-regression-live-dry-run` | Print preflight status and planned live routing commands. |
| `make routing-regression-live` | Run the local OpenClaw-backed routing regression gate. |
| `make skill-discovery` | Run online OpenClaw skill discovery + update generated shortlist section. |
| `make monthly-scorecard` | Regenerate monthly scorecard from eval/reliability/canary artifacts. |
| `make route-hygiene` | Enforce daily route hygiene guard (safe autofix + report artifact). |
| `make lane-hotspots` | Detect lane-wait hot windows and correlate cron jobs. |
| `make stop-gate-enforce` | Enforce canary stop gate and auto-disable promotion jobs after consecutive R1/R2 failures. |
| `make canary-stage` | Run one-shot staged canary harness with verdict artifact. |
| `make avatar`       | Preview or update your agent's avatar.             |
| `make audio-check`  | Test the audio (TTS) setup (ElevenLabs skill).     |
| `make lint`         | Run all lint and formatting checks (pre-commit).   |

## Orion March Compute Operations (2026-03)

Use this runbook during the March compute allocation window.

### Daily Monitors

Check these once per day and log outcomes in `eval/monthly-scorecard-2026-03.md`:

- Lane wait: p50 and p95 queue wait time by lane.
- Cron success/error: total runs, failures, and repeated error signatures.
- Delivery backlog: queued vs completed delivery tasks.
- Eval pass/delta: latest eval pass rate and score delta vs baseline.

### Stop Gates

Pause rollout work and escalate to ORION main if any gate is hit:

- Lane wait regression breaches team threshold for 2 consecutive checks.
- Cron failures persist across 2 consecutive scheduled runs.
- Delivery backlog grows day-over-day for 2 days without burn-down.
- Eval pass rate drops or eval delta shows net regression vs locked baseline.
- Any incident with external delivery correctness risk is unresolved.

### Weekly Cadence (Eval + Skill Canary Review)

Run once per week (recommended Monday):

1. Run full eval suite and archive artifacts.
2. Compare current report against previous weekly baseline.
3. Review skill canary outcomes, failure classes, and top regressions.
4. Record decisions, mitigations, and owner/date follow-ups in the monthly scorecard.

### Eval Commands

```bash
# Run full eval and emit latest report artifacts
make eval-run

# Compare two reports (example baseline vs latest)
make eval-compare BASE=eval/history/baseline-2026-03.json AFTER=eval/latest_report.json

# Capture a 24h runtime reliability snapshot
make eval-reliability

# Refresh monthly scorecard from current artifacts
make monthly-scorecard MONTH=2026-03

# Run route hygiene guard (safe autofix enabled)
make route-hygiene

# Detect top lane-wait hotspots and correlated cron runs
make lane-hotspots HOURS=24 TOP=10

# Enforce stop-gate disable action after consecutive reliability failures
make stop-gate-enforce MIN_FAIL_DAYS=2

# Run weekly online skill discovery update
make skill-discovery LIMIT=8

# Run one "coding party" batch (eval + reliability + canary health)
make party-batch-once

# Run one staged canary harness (set staged enable/rollback commands)
make canary-stage \
  CANDIDATE=openprose-workflow-2026-03 \
  STAGE_CMD='echo stage-ok' \
  ROLLBACK_CMD='echo rollback-ok'

# Optional: pass through extra harness flags
make canary-stage \
  CANDIDATE=openprose-workflow-2026-03 \
  STAGE_CMD='echo stage-ok' \
  HARNESS_ARGS='--skip-eval --skip-reliability'
```

## Pre-commit Checks

We use `pre-commit` to enforce code quality and formatting. Ensure hooks are installed and run:

```bash
# Install hooks (one-time)
pre-commit install

# Run lint and formatting checks on all files
make lint
# or
pre-commit run --all-files
```

Add or update hooks in `.pre-commit-config.yaml` as needed.

## Update Policy (Manual)

Updates are manual by default.

- Do not enable auto-updating behaviors until the gateway is stable and you explicitly want drift.
- When updating OpenClaw or skills, do it intentionally, record changes, and smoke test the gateway.

## Release Checklist

Before tagging and releasing a new version, perform the following:

1. **Update version & changelog**
   - Bump the version number in relevant files (e.g., `~/.openclaw/openclaw.json` notes + repository documentation).
   - Update `CHANGELOG.md` with new changes.
2. **Run tests and checks**
   ```bash
   make lint
   make soul
   ```
3. **Commit and tag**
   ```bash
   git add -A
   git commit -m "Release vX.Y.Z"
   git tag vX.Y.Z
   ```
4. **Push to remote**
   ```bash
   git push origin main --tags
   ```
5. **Verify deployment**
   - Ensure CI/CD passes.
   - Smoke test the gateway service.

---

## Memory Stack

The memory stack organizes notes and session data:

- **Working memory** (`memory/WORKING.md`): active task tracking
- **Long-term memory** (`MEMORY.md`): persistent notes and guardrails

On session start, the system should load `memory/WORKING.md` as working memory.

## Adding Skills

This repo stores OpenClaw skills under `skills/`.

Install/update skills manually, then smoke test the gateway.

## File-First Tickets (Repo-Native)

In addition to per-specialist inboxes (`tasks/INBOX/*.md`), ORION uses a repo-native,
file-first ticket workflow for durable execution tracking:

- Spec: `tasks/TICKETS.md`
- Intake (append-only): `tasks/INTAKE/`
- Lanes: `tasks/WORK/{backlog,in-progress,testing,done}/`
- Plan/status: `tasks/NOTES/plan.md`, `tasks/NOTES/status.md`

How this integrates with specialists:
- ORION creates/maintains the ticket file (the durable “what/why/done”).
- ORION delegates execution via `TASK_PACKET v1` in `tasks/INBOX/<AGENT>.md`,
  referencing the ticket path.
- Specialists update the ticket and drop artifacts under `tasks/WORK/artifacts/<ticket>/`,
  then add a `Result:` under the packet.
