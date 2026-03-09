# OpenClaw Config Migration

This project uses:
- Runtime config (JSON5): `~/.openclaw/openclaw.json`
- Repo reference templates (sanitized, no secrets):
  - `openclaw.yaml`
  - `openclaw.json.example`

## Scope

This migration moved schema-supported settings from `openclaw.yaml` into runtime config using `openclaw config set`.

## Migrated To Runtime

- `tools.profile = "coding"` (pin ORION to a local workspace posture; OpenClaw `2026.3.2` defaults new local installs to `messaging` when unset)
- `agents.defaults.model.primary = "google/gemini-2.5-flash-lite"` (pinned)
- `agents.defaults.model.fallbacks = ["google/gemini-2.5-flash-lite"]` (provider-restricted)
- `agents.defaults.workspace = "/Users/corystoner/Desktop/ORION"`
- `agents.list[0].subagents.allowAgents = ["atlas","node","pulse","stratus","pixel","quest","ember","ledger","polaris","scribe","wire"]` (explicit ORION delegation allowlist for `sessions_spawn`)
- `channels.telegram.enabled = true`
- `channels.telegram.commands.native = true`
- `channels.telegram.commands.nativeSkills = false`
- `channels.telegram.dmPolicy = "allowlist"`
- `channels.telegram.allowFrom = ["<CORY_TELEGRAM_USER_ID>"]`
- `channels.telegram.tokenFile = "~/.openclaw/secrets/telegram.token"`
- `channels.telegram.groupPolicy = "allowlist"`
- `channels.telegram.groupAllowFrom = ["<CORY_TELEGRAM_USER_ID>"]`
- `channels.telegram.groups = { "<TELEGRAM_GROUP_ID>": {} }`
- `channels.telegram.streamMode = "partial"`
- `channels.telegram.reactionLevel = "ack"`
- Optional (Discord):
  - `channels.discord.enabled = true`
  - `channels.discord.token = { source: "env", provider: "default", id: "DISCORD_BOT_TOKEN" }`
  - `channels.discord.dm.policy = "allowlist"`
  - `channels.discord.dm.allowFrom = ["<CORY_DISCORD_USER_ID>"]`
  - `channels.discord.groupPolicy = "allowlist"`
  - `channels.discord.guilds."<DISCORD_GUILD_ID>".channels."<DISCORD_PRIMARY_CHANNEL_ID>".allow = true`
  - `channels.discord.guilds."<DISCORD_GUILD_ID>".channels."<DISCORD_PRIMARY_CHANNEL_ID>".autoThread = true`

Non-required channels were removed from runtime config to keep the local gateway minimal.

## Config Validation (2026.3.2)

Use the new preflight validator before gateway start or after config edits:

```bash
openclaw config validate --json
```

This checks the live runtime config at `~/.openclaw/openclaw.json` without starting the gateway.

## Telegram Draft Streaming (March 2, 2026)

Telegram Bot API now includes `sendMessageDraft` for real-time draft streaming.
This repo wires that support into `scripts/telegram_send_message.sh` behind env flags:

- `TELEGRAM_STREAM_DRAFT=1`
- optional tuning: `TELEGRAM_STREAM_CHUNK_CHARS`, `TELEGRAM_STREAM_STEP_MS`
- optional: `TELEGRAM_STREAM_DRAFT_ID` (positive integer)

The script falls back to normal `sendMessage` if draft streaming is unsupported for a chat/bot.

## Not Migrated (Schema Or Install Specific)

All secrets and provider auth live outside the repo. Do not commit them.
For supported credential fields, prefer SecretRef objects over raw `${ENV}` strings so `openclaw secrets` audit/planning flows can reason about them directly.

## Auth Required For Model Routing

Current runtime model routing requires auth for:
- `google` (for `google/gemini-2.5-flash-lite`)

Set auth with either:
- `openclaw models auth login --provider <provider>`
- `openclaw models auth paste-token --provider <provider>`
Or via environment variables (`GEMINI_API_KEY`) if your gateway service is configured to inherit them.

## Verification Commands

```bash
openclaw models status
openclaw config get agents.defaults.workspace
openclaw config get 'agents.list[0].subagents.allowAgents'
openclaw config get channels.telegram
```
