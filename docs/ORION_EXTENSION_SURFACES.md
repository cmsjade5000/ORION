# ORION Extension Surfaces

ORION core is the admin-copilot and orchestration control plane. It is not the default home for product-specific Telegram features or domain-specific scheduled jobs.

## Core vs Extension

Core-owned surfaces:
- admin-copilot commands and inbox/task orchestration
- ATLAS/POLARIS/WIRE/SCRIBE routing
- delegated-job state, notifications, and maintenance loops
- safety, proof, and policy gates

Extension surfaces:
- trading and market workflows
- game-specific workflows
- media/recommendation mini-flows
- anything that adds its own user-facing command surface or recurring job family

## Current Non-Core Surfaces

These remain in the repo for now, but they are not part of the default ORION core runtime path:
- Kalshi and Polymarket scripts
- Pogo Telegram commands
- Flic Telegram commands and deep-link flow
- PIXEL and QUEST as conversational/product lanes

Concrete filesystem boundary in this workspace:
- extension Telegram surfaces live under `apps/extensions/telegram/`
- extension-facing product docs live under `apps/extensions/<surface>/docs/`
- core Telegram registration remains under `src/plugins/telegram/`

## Allowed Handoff Seams

Use one of these seams when core needs to interact with an extension:
- Task Packet handoff with explicit owner, stop gates, and proof requirements
- webhook/API handoff with a bounded input/output contract
- link or deep-link handoff where ORION stays the control plane but not the product host

## Rules

- Do not register extension Telegram commands on the default ORION core bot.
- Do not install extension scheduled jobs from the core maintenance installer.
- Do not route default daily ORION work through extension agents.
- If an extension needs its own runtime posture, give it its own workspace or installer path instead of widening ORION core.
