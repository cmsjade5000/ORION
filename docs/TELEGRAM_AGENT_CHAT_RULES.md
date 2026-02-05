# Telegram Agent Group Chat Rules & Onboarding Plan

This document defines the group chat conventions, agent roles, reaction mappings, and onboarding steps for inviting Gateway specialist agents into a shared Telegram group.

---
## 1. Bot Identities (Telegram Handles)

| Agent    | Bot Name                             | Telegram Link                        |
|:---------|:-------------------------------------|:-------------------------------------|
| **ORION**   | ORION (Primary Interface)           | @ORION_25_BOT (t.me/ORION_25_BOT)    |
| **ATLAS**   | ATLAS (Execution & Operations)      | @Atlas_GatewayBot                    |
| **PIXEL**   | PIXEL (Discovery & Tech)            | @Pixel_GatewayBot                    |
| **PULSE**   | PULSE (Workflow Orchestration)      | @Pulse_GatewayBot                    |
| **STRATUS** | STRATUS (Infrastructure & DevOps)   | @Stratus_GatewayBot                  |
| **EMBER**   | EMBER (Emotional Support)           | @Ember_GatewayBot                    |
| **LEDGER**  | LEDGER (Financial Insights)         | @Ledger_GatewayBot                   |
| **NODE***   | NODE (System Glue & Architecture)   | ·· (To be added)                     |

*NODE bot will be provisioned later.

---
## 2. Hierarchy & Speaking Protocol

1. **ORION** monitors all messages, orchestrates turn‑taking, and issues high‑level goals.
2. **Specialists** respond only when:
   - A comment or question falls within their domain (see Roles below).
   - They have a status update or critical finding to share.
3. **Turn‑taking rules:**
   - Agents avoid talking over each other—wait for Orion’s prompt if multiple speak.
   - Use direct mentions to request a specific agent: e.g., `@Atlas_GatewayBot, can you run ...?`.
4. **Rate limiting:**
   - Each agent should send no more than 5 messages per 30 minutes to avoid chat flooding.


1. **ORION** monitors all messages, orchestrates turn‑taking, and issues high‑level goals.
2. **Specialists** respond only when:
   - A comment or question falls within their domain (see Roles below).
   - They have a status update or critical finding to share.
3. **Turn‑taking rules:**
   - Agents avoid talking over each other—wait for Orion’s prompt if multiple speak.
   - Use direct mentions to request a specific agent: e.g., `@Atlas_GatewayBot, can you run ...?`.

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

1. **Generate Bot Tokens** via BotFather for each agent (ATLAS, PIXEL, PULSE, STRATUS, EMBER, LEDGER, NODE).
2. **Store credentials** in `keep/` as environment files:
   ```bash
   # keep/atlas.env
   ATLAS_TELEGRAM_TOKEN=<token>
   # keep/pixel.env
   PIXEL_TELEGRAM_TOKEN=<token>
   # ...and so on for pulse.env, stratus.env, ember.env, ledger.env, node.env
   ```
3. **Update `openclaw.yaml`** under the `telegram:` section to add each bot’s token and allowedChats entry.
4. **Reload OpenClaw** (or restart gateway) to apply the new bots configuration.
5. **Create Telegram group** and invite all agent bots and the user.
6. **Verify** each bot responds to `ping` or simple commands (e.g. `@Atlas_GatewayBot help`).

---
## 5. Questions & Concerns

- Do we need any additional change management or scheduling to invite all bots at once?
- Shall we include a group description or pinned rules for quick reference?
- Any permissions or privacy settings needed for the group (e.g. restricted invites)?


---
*Document created by ORION (Gateway orchestrator).*