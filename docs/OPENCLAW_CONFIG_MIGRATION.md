# OpenClaw Config Migration

This project uses:
- Runtime config (JSON5): `~/.openclaw/openclaw.json`
- Repo reference templates (sanitized, no secrets):
  - `openclaw.yaml`
  - `openclaw.json.example`

## Scope

This migration moved schema-supported settings from `openclaw.yaml` into runtime config using `openclaw config set`.

## Migrated To Runtime

- `tools.profile = "coding"` (pin ORION to a local workspace posture; as of OpenClaw `2026.3.x`, new local installs default to `messaging` when unset)
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

## Config Validation (OpenClaw 2026.3.x)

Use the new preflight validator before gateway start or after config edits:

```bash
openclaw config validate --json
```

This checks the live runtime config at `~/.openclaw/openclaw.json` without starting the gateway.

## Codex 0.114.0 Compatibility Notes

Codex `0.114.0` changed a few runtime behaviors that matter to ORION-style orchestration:

- Handoffs now inherit realtime transcript context. Keep Task Packets concise and avoid stuffing the full prior transcript into delegation templates.
- `request_permissions` approvals now persist across turns, work with reject-style configs, and preserve legacy `workspace-write` behavior on older builds. ORION policy stays the same: security gates still come from `SECURITY.md` and `TOOLS.md`.
- The runtime still exposes the `$` mention picker, but operator-facing docs/prompts should standardize on `@plugin` mention style.
- If you run a websocket app-server alongside ORION automation, health probes should target `GET /readyz` and `GET /healthz` on that listener.

This repo keeps those changes backwards-tolerant by treating them as additive runtime capabilities, not permission relaxations.

## Compatibility Note (OpenClaw 2026.3.x): `gateway.auth.mode`

As of OpenClaw `2026.3.x`, runtime config requires explicit `gateway.auth.mode` when both auth
credentials exist. Keep this pinned to avoid ambiguous auth startup failures:

```bash
openclaw config get gateway.auth
```

Expected shape:

```json
{ "mode": "token", "token": "..." }
```

If needed:

```bash
openclaw config set gateway.auth.mode token
```

## Telegram Topic Routing (OpenClaw 2026.3.x)

OpenClaw now supports topic-level `agentId` routing under:

- `channels.telegram.groups.<chatId>.topics.<topicId>.agentId`

Template examples are documented in:

- `openclaw.yaml`
- `openclaw.json.example`
- `docs/TELEGRAM_TOPIC_ROUTING.md`

Bootstrap helper in this repo:

```bash
scripts/telegram_topic_bindings_bootstrap.sh \
  --group-id -1001234567890 \
  --topic 1:main \
  --topic 7:atlas
```

Apply:

```bash
scripts/telegram_topic_bindings_bootstrap.sh \
  --group-id -1001234567890 \
  --topic 1:main \
  --topic 7:atlas \
  --apply
```

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
openclaw sessions cleanup --agent main --dry-run --fix-missing --json
openclaw agents bindings --json
```

If a Codex websocket app-server is in front of automation flows, also verify:

```bash
curl -fsS "${CODEX_APP_SERVER_BASE_URL%/}/readyz"
curl -fsS "${CODEX_APP_SERVER_BASE_URL%/}/healthz"
```
