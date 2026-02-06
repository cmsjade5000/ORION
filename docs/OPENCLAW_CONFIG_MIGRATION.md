# OpenClaw Config Migration

This project uses:
- Runtime config: `~/.openclaw/openclaw.json`
- Repo reference template: `openclaw.yaml`

## Scope

This migration moved schema-supported settings from `openclaw.yaml` into runtime config with `openclaw config set`.

## Migrated To Runtime

- `agents.defaults.model.primary = "openrouter/openrouter/auto"`
- `agents.defaults.model.fallbacks = ["google/gemini-2.5-flash-lite"]`
- `channels.telegram.enabled = true`
- `channels.slack.enabled = false`
- `channels.telegram.dmPolicy = pairing`
- `channels.telegram.groupPolicy = allowlist`
- `channels.telegram.groupAllowFrom = ["8471523294"]`
- `channels.telegram.groups = {"-1003742519270": {}}`
- `channels.telegram.reactionLevel = ack`
- `channels.telegram.streamMode = partial`
- `tools.agentToAgent.enabled = true`
- `tools.agentToAgent.allow = ["main"]`
- `messages.tts.auto = off` (mapped from legacy `messages.tts.enabled: false`)
- `plugins.entries.whatsapp.enabled = false`
- `plugins.entries.slack.enabled = false`
- `plugins.entries.telegram.enabled = true`

## Not Migrated (Schema Or Install Specific)

- `tools.mino.apiKeyFile`
- `pulse.*` block
- `memory.backends.qmd.*` block
- `openrouter.api_key`
- `channels.whatsapp.enabled` (not a valid key in this install; WhatsApp is disabled via `plugins.entries.whatsapp.enabled = false`)

These are still kept in `openclaw.yaml` as project-level references and should only be migrated when corresponding runtime schema support is present.

## Auth Required For Model Routing

Current runtime model routing requires auth for:
- `openrouter` (for `openrouter/openrouter/auto`)
- `google` (for `google/gemini-2.5-flash-lite` fallback)

Set auth with either:
- `openclaw models auth login --provider <provider>`
- `openclaw models auth paste-token --provider <provider>`

## Verification Commands

```bash
openclaw models status
openclaw config get channels.telegram
openclaw config get channels.slack
openclaw config get tools.agentToAgent
openclaw config get plugins.entries
openclaw config get messages.tts
```
