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
   cd gateway
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
   - Copy `keep/telegram.env.sample` to `keep/telegram.env` and set your Telegram bot token.
   - Copy `keep/slack.env.sample` to `keep/slack.env` and set your Slack credentials.
   - Review `openclaw.yaml` to enable/disable channels and configure allowed chats.

## Daily Commands

Use the top-level Makefile aliases to streamline common tasks:

| Command             | Description                                        |
|---------------------|----------------------------------------------------|
| `make dev`          | Start or resume the OpenClaw gateway service.      |
| `make restart`      | Restart the OpenClaw gateway service.              |
| `make soul`         | Regenerate all agent `SOUL.md` identity files.     |
| `make routingsim`   | View and run the routing simulation exercise.      |
| `make avatar`       | Preview or update your agent's avatar.             |
| `make audio-check`  | Test the audio (TTS) setup.                        |
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

## Release Checklist

Before tagging and releasing a new version, perform the following:

1. **Update version & changelog**
   - Bump the version number in relevant files (e.g., `openclaw.yaml`, documentation).
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
