# Telegram Agent Group Chat Rules & Onboarding Plan

This document defines the group chat conventions, agent roles, reaction mappings, and onboarding steps for inviting Gateway specialist agents into a shared Telegram group.

**Current mode:** Single bot only (ORION). Multi-bot group chat is deferred. Keep the multi-bot sections below as a future plan.
For the main onboarding path and runtime checks, use [docs/ORION_START_HERE.md](/Users/corystoner/src/ORION/docs/ORION_START_HERE.md).

---
## 1. Bot Identities (Telegram Handles)

Active now:

| Agent    | Bot Name                             | Telegram Link                        |
|:---------|:-------------------------------------|:-------------------------------------|
| **ORION**   | ORION (Gateway Orchestrator)        | @Orion_GatewayBot (t.me/Orion_GatewayBot)    |

**Note:** Specialists do not have Telegram access in the current runtime. ORION invokes them internally via swarm/session tools.

Current Telegram commands (implemented by the Telegram plugin, not by specialist chat bots):
- `/today` returns today's agenda from local assistant artifacts.
- `/capture <text>` queues a quick admin capture to POLARIS.
- `/followups` summarizes waiting-on items and POLARIS queue state.
- `/review` returns a bounded daily review.
- `/orion` opens the ORION Main Mini App.
- `/dreaming status|on|off|help` inspects or updates ORION's dreaming config via the local assistant command path.
- `/agents` shows the Agent Dashboard inline keyboard.

Extension-only Telegram surfaces are intentionally outside the default ORION core bot path:
- Flic, Kalshi, and Pogo command handlers now live under `apps/extensions/telegram/`
- they are not registered by `src/plugins/telegram/index.ts`
- enable them only in an extension runtime or a product-specific bot surface

---
## 2. Hierarchy & Speaking Protocol

1. **ORION** is the only bot responding in Telegram right now.
2. **Specialists** are invoked internally by ORION and do not speak directly in Telegram.
3. If Telegram ever becomes multi-bot again, treat that as a separate project rather than part of default onboarding.

---
## 3. Tapback Reaction Guidelines

Supported Tapbacks (reactions):

| Tapback | Meaning                        |
|:--------|:-------------------------------|
| 👍       | Acknowledged / understood       |
| 👀       | Investigating / in progress     |
| ❤️       | Appreciation / endorsement      |

For warnings or completions, agents should reply inline with plain text status instead of adding decorative emoji.

---
## 4. Onboarding & Token Configuration

For the full first-time walkthrough, start at [docs/ORION_START_HERE.md](/Users/corystoner/src/ORION/docs/ORION_START_HERE.md). This section is the Telegram-specific appendix.

1. **Generate Bot Token** via BotFather for ORION.
2. **Store token** in a token file (plain token value only):
   ```bash
   mkdir -p ~/.openclaw/secrets
   printf '%s\n' '<telegram-bot-token>' > ~/.openclaw/secrets/telegram.token
   chmod 600 ~/.openclaw/secrets/telegram.token
   ```
3. **Update `~/.openclaw/openclaw.json`** under `channels.telegram` to set `tokenFile` to that path and configure allowed groups/users.
4. **Reload OpenClaw** (or restart gateway) to apply the configuration.
5. **Create Telegram group** and invite ORION and the user (if using a group).
6. **Verify** ORION responds:
   - `ping` (basic liveness), and
   - `/agents` (dashboard),
   - `/orion` (Mini App launch).
