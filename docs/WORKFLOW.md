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
   - See `docs/OPENCLAW_CONFIG_MIGRATION.md` for mapping details.
   - For single-bot delegation behavior, follow `docs/ORION_SINGLE_BOT_ORCHESTRATION.md`.
   - For delegation structure, follow `docs/TASK_PACKET.md` and `tasks/INBOX/`.
   - Optional Mini App dashboard:
     - Set `ORION_MINIAPP_URL` (deployed HTTPS URL). ORION exposes `/miniapp`.
     - See `apps/telegram-miniapp-dashboard/README.md` for deployment + security notes.
   - For best gateway-service reliability, store model/provider auth using `openclaw models auth paste-token` (LaunchAgent services may not inherit your shell env vars).
   - For email, follow `docs/EMAIL_POLICY.md` (ORION-only inbox; threat preflight; draft-first outbound).
   - For outages/power failures/manual restart, follow `docs/RECOVERY.md` (and use `./status.sh` for a fast local+AEGIS snapshot).

6. **Go live locally (recommended order)**
   ```bash
   openclaw gateway install
   openclaw gateway start
   openclaw doctor --repair
   openclaw security audit --deep
   openclaw channels status --probe
   openclaw agents list --bindings
   ```

## Daily Commands

Use the top-level Makefile aliases to streamline common tasks:

| Command             | Description                                        |
|---------------------|----------------------------------------------------|
| `make dev`          | Start or resume the OpenClaw gateway service.      |
| `make restart`      | Restart the OpenClaw gateway service.              |
| `make soul`         | Regenerate all agent `SOUL.md` identity files.     |
| `make routingsim`   | View and run the routing simulation exercise.      |
| `make avatar`       | Preview or update your agent's avatar.             |
| `make audio-check`  | Test the audio (TTS) setup (ElevenLabs skill).     |
| `make lint`         | Run all lint and formatting checks (pre-commit).   |

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
