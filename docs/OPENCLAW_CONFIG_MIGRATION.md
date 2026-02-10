# OpenClaw Config Migration

This project uses:
- Runtime config (JSON5): `~/.openclaw/openclaw.json`
- Repo reference templates (sanitized, no secrets):
  - `openclaw.yaml`
  - `openclaw.json.example`

## Scope

This migration moved schema-supported settings from `openclaw.yaml` into runtime config using `openclaw config set`.

## Migrated To Runtime

- `agents.defaults.model.primary = "google/gemini-2.5-flash-lite"` (pinned)
- `agents.defaults.model.fallbacks = ["google/gemini-2.5-flash-lite"]` (provider-restricted)
- `agents.defaults.workspace = "/Users/corystoner/Desktop/ORION"`
- `agents.list[0].subagents.allowAgents = ["*"]` (so ORION can target specialists via `sessions_spawn`)
- `channels.telegram.enabled = true`
- `channels.telegram.commands.native = false` (avoid Telegram bot command registration churn)
- `channels.telegram.commands.nativeSkills = false`
- `channels.telegram.dmPolicy = "allowlist"`
- `channels.telegram.allowFrom = ["<CORY_TELEGRAM_USER_ID>"]`
- `channels.telegram.tokenFile = "~/.openclaw/secrets/telegram.token"`
- `channels.telegram.groupPolicy = "allowlist"`
- `channels.telegram.groupAllowFrom = ["<CORY_TELEGRAM_USER_ID>"]`
- `channels.telegram.groups = { "<TELEGRAM_GROUP_ID>": {} }`
- `channels.telegram.streamMode = "partial"`
- `channels.telegram.reactionLevel = "ack"`

Non-required channels were removed from runtime config to keep the local gateway minimal.

## Not Migrated (Schema Or Install Specific)

All secrets and provider auth live outside the repo. Do not commit them.

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
