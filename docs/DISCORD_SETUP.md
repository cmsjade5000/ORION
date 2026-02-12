# Discord Setup (ORION)

Goal: make Discord feel as native as Telegram in this workspace (fast inbound, clean thread routing, safe allowlists).

## Concept Map

- Discord DM: `user:<discord_user_id>` (private conversation)
- Discord channel: `channel:<channel_id>` (shared room)
- Discord thread: `channel:<thread_id>` (task context; preferred)

OpenClaw treats Discord threads as channels with their own IDs. If you keep talking in a thread, the session stays in that thread.

## Create App + Bot (Discord Dev Portal)

1. Create an application at the Discord Developer Portal.
2. Add a Bot to the application.
3. Copy the Bot Token (keep it out of Git).
4. Intents (Bot → Privileged Gateway Intents):
   - DMs: typically work without Message Content intent.
   - Guild text messages (freeform): enable **Message Content Intent**.
   - If you cannot enable it, use mention-gating (`requireMention=true`) or native commands.

## Recommended Server Layout (Your Posture)

- `#orion` (primary): you post requests here; ORION auto-creates a thread per request.
- `#orion-updates` (updates): ORION posts proactive/async updates here (no threads by default).

## Invite The Bot To A Server

OAuth2 URL Generator:
- Scopes: `bot`, `applications.commands`
- Permissions (minimum typical set):
  - View Channels
  - Send Messages
  - Send Messages in Threads
  - Create Public Threads (and/or Create Private Threads, depending on your server policy)
  - Read Message History
  - Attach Files (if you want file uploads)

Tip: to get `guild_id` / `channel_id`, enable Developer Mode in Discord (Settings → Advanced), then right-click the server/channel → "Copy ID".

## Enable The OpenClaw Discord Plugin

OpenClaw ships a bundled Discord channel plugin, but it’s disabled by default:

```bash
openclaw plugins enable discord
openclaw gateway restart
```

## Configure OpenClaw (Recommended Secure Defaults)

Store your token in `~/.openclaw/.env`:

```bash
printf '%s\n' 'DISCORD_BOT_TOKEN=***' >> ~/.openclaw/.env
chmod 600 ~/.openclaw/.env
```

Then set config:

```bash
openclaw config set channels.discord.enabled true
openclaw config set channels.discord.token '${DISCORD_BOT_TOKEN}'

# DM allowlist (recommended for personal use)
openclaw config set channels.discord.dm.policy allowlist
openclaw config set channels.discord.dm.allowFrom '["<CORY_DISCORD_USER_ID>"]'

# Guild/channel allowlist (recommended)
openclaw config set channels.discord.groupPolicy allowlist
openclaw config set channels.discord.guilds."<DISCORD_GUILD_ID>".requireMention false
openclaw config set channels.discord.guilds."<DISCORD_GUILD_ID>".channels."<DISCORD_PRIMARY_CHANNEL_ID>".allow true
openclaw config set channels.discord.guilds."<DISCORD_GUILD_ID>".channels."<DISCORD_UPDATES_CHANNEL_ID>".allow true

# Task UX: auto-create a thread per new request in this channel
openclaw config set channels.discord.guilds."<DISCORD_GUILD_ID>".channels."<DISCORD_PRIMARY_CHANNEL_ID>".autoThread true
openclaw config set channels.discord.guilds."<DISCORD_GUILD_ID>".channels."<DISCORD_UPDATES_CHANNEL_ID>".autoThread false

# Optional: reply threading style (nested replies)
openclaw config set channels.discord.replyToMode first

# Proactive updates target (used by scripts/notify_inbox_results.py)
export DISCORD_DEFAULT_POST_TARGET="channel:<DISCORD_UPDATES_CHANNEL_ID>"
```

## Verify

```bash
openclaw channels status --probe --json
openclaw channels resolve --channel discord "<DISCORD_CHANNEL_ID>" --json
```

## Common Failures

- Plugin not enabled: `openclaw plugins list --json` shows `discord` disabled.
- Missing token / wrong token: channel shows configured=false or probe fails.
- Bot can DM but won’t respond in channels:
  - Channel/guild not allowlisted, or `groupPolicy` is `disabled`.
  - Missing permissions in the channel.
  - Message Content intent disabled/limited and you’re expecting freeform channel messages; use `requireMention`, native commands, or enable the intent.
- Thread creation fails:
  - Bot lacks thread permissions (Create Public/Private Threads, Send Messages in Threads).

## Manual Test Checklist (Acceptance)

1. DM test:
   - DM the bot: “Ping ORION”
   - Expect a reply within ~5–15s.
2. Channel test (allowed channel):
   - Post a request (no mention needed when `requireMention=false` and Message Content intent is enabled).
   - Expect ORION to reply and, if `autoThread=true`, a task thread is created and used.
3. Thread task test:
   - Continue the conversation inside the created thread.
   - Expect subsequent replies to remain in the same thread.
4. Multi-agent update test:
   - Ask ORION for something that delegates (e.g., “Run gateway diagnostics via ATLAS”).
   - Expect updates in the same thread, with sub-agent sections clearly tagged (e.g., `[ATLAS] ...`).
5. Failure mode test:
   - Try in a non-allowlisted channel; expect no response.
