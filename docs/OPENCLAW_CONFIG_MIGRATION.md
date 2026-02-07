# OpenClaw Config Migration

This project uses:
- Runtime config (JSON5): `~/.openclaw/openclaw.json`
- Repo reference template: `openclaw.yaml` (sanitized, no secrets)

## Scope

This migration moved schema-supported settings from `openclaw.yaml` into runtime config using `openclaw config set`.

## Migrated To Runtime

- `agents.defaults.model.primary = "openrouter/openrouter/auto"`
- `agents.defaults.model.fallbacks = ["google/gemini-2.5-flash-lite"]`
- `agents.defaults.workspace = "/Users/corystoner/Desktop/ORION"`
- `channels.telegram.enabled = true`
- `channels.telegram.dmPolicy = "pairing"`
- `channels.telegram.tokenFile = "~/.openclaw/secrets/telegram.token"`
- `channels.telegram.groupPolicy = "allowlist"`
- `channels.telegram.groupAllowFrom = ["<CORY_TELEGRAM_USER_ID>"]`
- `channels.telegram.groups = { "<TELEGRAM_GROUP_ID>": {} }`
- `channels.telegram.streamMode = "partial"`
- `channels.telegram.reactionLevel = "ack"`
- `tools.agentToAgent.enabled = true`
- `tools.agentToAgent.allow = ["main", "atlas", "node", "pulse", "stratus", "pixel", "ember", "ledger"]`

## Not Migrated (Schema Or Install Specific)

All secrets and provider auth live outside the repo. Do not commit them.

## Auth Required For Model Routing

Current runtime model routing requires auth for:
- `openrouter` (for `openrouter/openrouter/auto`)
- `google` (for `google/gemini-2.5-flash-lite` fallback)

Set auth with either:
- `openclaw models auth login --provider <provider>`
- `openclaw models auth paste-token --provider <provider>`
Or via environment variables (`OPENROUTER_API_KEY`, `GEMINI_API_KEY`) if your gateway service is configured to inherit them.

## Verification Commands

```bash
openclaw models status
openclaw config get agents.defaults.workspace
openclaw config get channels.telegram
openclaw config get tools.agentToAgent
```
