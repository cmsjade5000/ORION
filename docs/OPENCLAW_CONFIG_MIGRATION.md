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
- `agents.defaults.model.primary = "openrouter/openrouter/free"` (low-cost default)
- `agents.defaults.model.fallbacks = ["openai/gpt-oss-20b:free","minimax/MiniMax-M2.7-highspeed","minimax/MiniMax-M2.7"]` (cheap/free-first)
- `agents.defaults.workspace = "/Users/corystoner/src/ORION"`
- `agents.defaults.subagents.maxConcurrent = 11` (keep native parallel delegation aligned with the live runtime)
- `agents.defaults.subagents.maxSpawnDepth = 2` (allow ATLAS-owned depth-1 recursion without making ORION itself recursive)
- `agents.list[0].subagents.allowAgents = ["atlas","ember","ledger","polaris","scribe","wire"]` (explicit ORION core delegation allowlist for `sessions_spawn`)
- `agents.list[1].subagents.allowAgents = ["node","pulse","stratus"]` (ATLAS-only recursive child surface)
- `hooks.internal.enabled = ["session-memory","command-logger"]`
- `channels.telegram.enabled = true`
- `channels.telegram.commands.native = true`
- `channels.telegram.commands.nativeSkills = false`
- `channels.telegram.dmPolicy = "allowlist"`
- `channels.telegram.allowFrom = ["<CORY_TELEGRAM_USER_ID>"]`
- `channels.telegram.tokenFile = "~/.openclaw/secrets/telegram.token"`
- `channels.telegram.groupPolicy = "allowlist"`
- `channels.telegram.groupAllowFrom = ["<CORY_TELEGRAM_USER_ID>"]`
- `channels.telegram.groups = { "<TELEGRAM_GROUP_ID>": {} }`
- `channels.telegram.streaming = "partial"`
- `channels.telegram.reactionLevel = "ack"`
- `plugins.slots.memory = "memory-lancedb"`
- `plugins.entries."memory-lancedb".enabled = true`
- `plugins.entries."memory-lancedb".config.embedding.apiKey = "${OPENROUTER_API_KEY}"`
- `plugins.entries."memory-lancedb".config.embedding.baseUrl = "https://openrouter.ai/api/v1"`
- `plugins.entries."memory-lancedb".config.embedding.model = "text-embedding-3-small"`
- `plugins.entries."memory-core".enabled = false` (reserved for a dreaming pilot; not the active slot)
- `plugins.entries."memory-core".config.dreaming.enabled = false`
- `plugins.entries."memory-core".config.dreaming.frequency = "0 3 * * *"`
- `plugins.entries."open-prose".enabled = true`
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

Recommended assistant-specific checks:

```bash
openclaw hooks list
openclaw plugins list --json
openclaw agents bindings --json
openclaw config get 'agents.defaults.subagents'
```

## Operational Notes (OpenClaw 2026.4.14)

Latest local upgrade verification: 2026-04-14 on ORION's Mac runtime.

Important upstream behavior changes for this workspace:

- Isolated cron deadlock handling improved in `2026.3.13`, which benefits assistant agenda refresh, inbox notify, and follow-through loops.
- Cross-agent workspace resolution improved for subagent spawns, which pairs with this repo's canonical `/Users/corystoner/src/ORION` workspace path.
- Agent memory injection was hardened on case-insensitive filesystems, which matters on macOS.
- Gateway health/reporting is stricter around degraded reachability and unanswered client requests.
- Channel/binding collisions now fail fast, so `openclaw agents bindings --json` is part of the recommended post-change check path.
- OpenClaw `2026.4.14` keeps bundled Codex provider support, Active Memory, and `commands.list`, and the release train materially improved plugin loading plus memory/dreaming reliability.
- On 2026-04-14, `openclaw gateway install --force` still generated a LaunchAgent plist with embedded `OPENCLAW_GATEWAY_TOKEN`; treat `gateway-token-embedded` from `openclaw gateway status --json` as an upstream installer regression until a follow-up release clears the audit.

See:
- `docs/OPENCLAW_2026_3_13_UPGRADE_NOTES.md`

## Memory Plugin Note

`memory-lancedb` no longer boots with `enabled = true` alone. It requires an
explicit `embedding` config block.

Practical rule:

- If you use OpenRouter for embeddings, keep the model string bare:
  `text-embedding-3-small`
- Do not use provider-prefixed forms such as
  `openai/text-embedding-3-small`; the plugin rejects them before startup.
- This plugin schema currently expects a plain string API key, so `${ENV}`
  interpolation is the portable runtime pattern here rather than a `SecretRef`
  object.

## Dreaming Pilot Note (OpenClaw 2026.4.5)

OpenClaw `2026.4.14` continues to expose dreaming under `plugins.entries.memory-core.config.dreaming`.

Practical ORION rule:
- Do not flip `plugins.slots.memory` from `memory-lancedb` to `memory-core` casually.
- Keep dreaming disabled in the template until the active memory backend is stable enough for background promotion.
- When piloting, use only the documented public keys:
  - `enabled`
  - `frequency`
- After any OpenClaw config change, run `make operator-health-bundle` so gateway, model, and memory health stay aligned.
- Live provider probes and smoke turns are opt-in: set `ALLOW_LIVE_MODEL_PROBE=1` and/or `ALLOW_LIVE_SMOKE=1` when you intentionally want token-spending checks.
- ORION repo planning and code-mod work should stay in low-cost mode by default: local context first, targeted verification only, no automatic paid probes.

Observed official surfaces:
- Slash command: `/dreaming on|off|status|help`
- CLI review path:
  - `openclaw memory status --deep`
  - `openclaw memory promote`
  - `openclaw memory promote-explain`
  - `openclaw memory rem-harness`

Operational caution:
- `MEMORY.md` remains the durable truth file.
- `DREAMS.md` is a review diary and should not be treated as a truth source by default.

See:
- `docs/OPENCLAW_MEMORY_DREAMING.md`

## Codex 0.114.x Compatibility Notes

Latest local verification (2026-03-12): `codex-cli 0.114.0` via Homebrew cask.

Codex `0.114.x` introduced runtime behaviors that matter to ORION-style orchestration:

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
- `openrouter` (for `openrouter/openrouter/free` and `openrouter/auto`)
- optional `openai` (only when you intentionally enable a premium OpenAI lane)
- optional `openai-codex` (only when you intentionally enable Codex/OAuth lanes)

Set auth with either:
- `openclaw models auth login --provider <provider>`
- `openclaw models auth paste-token --provider <provider>`
For script-driven eval lanes, you may also use environment variables such as `OPENAI_API_KEY` or `OPENROUTER_API_KEY` when your gateway service is configured to inherit them.

## Verification Commands

```bash
openclaw models status
openclaw hooks list
openclaw plugins list --json
openclaw config get agents.defaults.workspace
openclaw config get 'agents.defaults.subagents'
openclaw config get 'agents.list[0].subagents.allowAgents'
openclaw config get 'agents.list[1].subagents.allowAgents'
openclaw config get 'hooks.internal.enabled'
openclaw config get 'plugins.slots.memory'
openclaw config get channels.telegram
openclaw sessions cleanup --agent main --dry-run --fix-missing --json
openclaw agents bindings --json
```

If a Codex websocket app-server is in front of automation flows, also verify:

```bash
curl -fsS "${CODEX_APP_SERVER_BASE_URL%/}/readyz"
curl -fsS "${CODEX_APP_SERVER_BASE_URL%/}/healthz"
```
