# Telegram Agent Group Chat Rules & Onboarding Plan

This document defines the group chat conventions, agent roles, reaction mappings, and onboarding steps for inviting Gateway specialist agents into a shared Telegram group.

**Current mode:** Single bot only (ORION). Multi-bot group chat is deferred. Keep the multi-bot sections below as a future plan.

---
## 1. Bot Identities (Telegram Handles)

Active now:

| Agent    | Bot Name                             | Telegram Link                        |
|:---------|:-------------------------------------|:-------------------------------------|
| **ORION**   | ORION (Primary Interface)           | @ORION_25_BOT (t.me/ORION_25_BOT)    |

**Note:** Specialists do not have Telegram access in the current runtime. ORION invokes them internally via swarm/session tools.

---
## 2. Hierarchy & Speaking Protocol

1. **ORION** is the only bot responding in Telegram right now.
2. **Specialists** are invoked internally by ORION and do not speak directly in Telegram.
3. **Future (multi-bot) rules** remain below once multi-bot is re-enabled.

### Agent Roles & Triggers
- **ATLAS:** Executes and reports on operational tasks (installations, smoke tests, automation).
- **PIXEL:** Shares discovery, research, and tech evaluations (new projects, demos).
- **PULSE:** Posts workflow/job status updates (heartbeats, retries, alerts).
- **STRATUS:** Announces infra provisioning, CI/CD status, and environment changes.
- **EMBER:** Offers emotional grounding or check‑ins if conversation signals stress.
- **LEDGER:** Provides financial cost analyses, budget alerts, and trade‑off insights.
- **NODE:** Addresses architecture/code organization questions (to be enabled later).

---
## 3. Tapback Reaction Guidelines

Supported Tapbacks (reactions):

| Tapback | Meaning                        |
|:--------|:-------------------------------|
| 👍       | Acknowledged / understood       |
| 👀       | Investigating / in progress     |
| ❤️       | Appreciation / endorsement      |
| 👎       | Disapproval / skip              |
| 🔥       | Highlight or urgent             |

For warnings (⚠️) and completions (✅), agents should reply inline with clear messages rather than using Tapbacks.

---
## 4. Onboarding & Token Configuration

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
6. **Verify** ORION responds to `ping` or simple commands.

---
## 5. Questions & Concerns

- When we re-enable multi-bot Telegram, do we want separate bot tokens per specialist or keep specialists internal-only and add only one more bot at a time?
- Do we want a pinned group rules message at that time (roles + reactions + safety)?
