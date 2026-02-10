# Scripts

This directory contains maintenance, build, and automation scripts for the Gateway system.

Scripts here are intended to be:
- explicit
- repeatable
- safe to run locally
- version-controlled

Nothing in this directory should modify secrets directly.

---

## discord_selfcheck.sh

### Purpose
Verifies that OpenClaw's Discord plugin is enabled and `channels.discord` is configured safely (best-effort probe; does not print tokens).

### Usage

```bash
./scripts/discord_selfcheck.sh
```

---

## discord_send_message.sh

### Purpose
Send a Discord message via OpenClaw's Discord channel plugin.

### Usage

```bash
./scripts/discord_send_message.sh user:<DISCORD_USER_ID> "hi"
./scripts/discord_send_message.sh channel:<DISCORD_CHANNEL_ID> "update"
```

Read message from stdin:

```bash
printf '%s\n' "multi-line\nmessage" | ./scripts/discord_send_message.sh channel:<DISCORD_CHANNEL_ID> -
```

---

## discord_thread_create.sh

### Purpose
Create a task thread in a Discord channel via OpenClaw.

### Usage

```bash
./scripts/discord_thread_create.sh channel:<DISCORD_CHANNEL_ID> "task: triage" "starting thread"
```

---

## discord_thread_reply.sh

### Purpose
Reply in an existing Discord thread via OpenClaw.

### Usage

```bash
./scripts/discord_thread_reply.sh channel:<DISCORD_THREAD_ID> "progress update"
```

---

## miniapp_upload_artifact.sh

### Purpose
Uploads a file (PDF/export/etc.) to the Telegram Mini App dashboard API so it appears as a floating artifact bubble that the user can tap to download.

### Usage

```bash
INGEST_TOKEN=... ./scripts/miniapp_upload_artifact.sh https://<miniapp-host> ./out/xyz.pdf xyz.pdf application/pdf LEDGER
```

---

## telegram_open_miniapp.sh

### Purpose
Sends an inline `web_app` button to the allowlisted Telegram user so you can open the Mini App without hunting for the URL.

### Usage

```bash
./scripts/telegram_open_miniapp.sh
```

Optional URL override:

```bash
./scripts/telegram_open_miniapp.sh https://<miniapp-host>
```

---

## soul_factory.sh

### Purpose
`soul_factory.sh` generates per-agent `SOUL.md` files from modular source-of-truth identity components.

It combines:
- shared constitutional rules
- shared foundational identity
- shared routing logic
- a single agent role definition

into a final, agent-specific `SOUL.md`.

---

### Source of Truth

Inputs:
- `src/core/shared/`
- `src/agents/`

Output:
- `agents/<AGENT>/SOUL.md`

Generated files should never be edited by hand.

---

### Usage

Generate SOULs for all agents:
```bash
./scripts/soul_factory.sh --all
