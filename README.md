# Gateway

Gateway is a personal, local-first agent orchestration system.

It provides a secure, modular environment where multiple AI agents collaborate under a single coordinating interface to help with planning, execution, discovery, emotional regulation, and financial decision-making.

This system is designed to be:
- intentional
- auditable
- cost-aware
- resistant to drift

Gateway runs locally on the Mac mini (macOS) and is backed by Git for transparency and long-term maintainability.

---

## What Problem This Solves

Most AI “agent systems” suffer from:
- unclear authority and overlap
- massive prompt bloat and token waste
- identity drift over time
- poor separation between planning and execution
- weak security and secret handling

Gateway addresses these by:
- using a single primary interface agent (ORION)
- clearly scoping specialist agents
- enforcing shared constitutional rules
- generating agent identities from modular source files
- keeping secrets and execution boundaries explicit

---

## High-Level Architecture

User (Telegram / CLI / UI)
|
v
ORION
|
+–> EMBER   (mental health, grounding)
+–> ATLAS   (execution, ops)
+–> PIXEL   (discovery, tech, culture)
+–> NODE    (system glue, architecture)
+–> LEDGER  (money, value, finance)

ORION interprets intent, delegates to specialists, integrates responses, and presents a coherent outcome to the user.

Current runtime mode is single-bot ingress: only ORION is Telegram-facing; specialists run through internal delegated sessions.

---

## Repository Structure

ORION/
├── README.md        # This file
├── VISION.md        # Long-term intent and guiding principles
├── SECURITY.md      # Threat model and trust boundaries
├── KEEP.md          # Secrets doctrine
├── USER.md          # User preferences and authority
├── IDENTITY.md      # ORION identity metadata (avatar, tone, etc.)
├── MEMORY.md        # Long-term memory policy notes
│
├── src/             # Application source code
│   ├── core/        # Core modules (shared logic and routing)
│   ├── agents/      # Agent role definitions (source of truth)
│   ├── plugins/     # Plugin modules
│   ├── memory/      # Memory backends
│   └── skills/      # Skill implementations
│
├── agents/          # Generated agent artifacts (SOUL.md)
├── docs/            # System and workflow documentation
├── memory/          # Working + daily memory artifacts
├── tasks/           # Task queue and execution artifacts
│
├── scripts/         # Build and maintenance scripts
│   └── soul_factory.sh
│
└── keep/            # Local-only secrets storage (not committed)

---

## Memory Backends

Memory currently uses the local `memory/` folder only. QMD integration is deferred for now.

---

## Agent Model

Gateway uses a modular **SOUL architecture** to avoid prompt bloat and identity drift.

Each agent’s final `SOUL.md` is generated from:
- shared constitutional rules
- shared foundational identity
- shared routing logic
- a minimal role-specific layer

This allows:
- consistent behavior across agents
- low and predictable token overhead
- system-wide updates without drift
- clean Git diffs and rollbacks

---

## Soul Factory

Agent SOULs are generated via the Soul Factory script.

To regenerate all agents:
./scripts/soul_factory.sh --all

Source files live in:
- `src/core/shared/`
- `src/agents/`

Generated output lives in:
- `agents/<AGENT>/SOUL.md`

---

## What This Is Not

Gateway is **not**:
- an autonomous system acting without user intent
- a replacement for professional medical or financial advice
- a cloud-first or SaaS-dependent platform
- a black box with hidden state

Human authority, transparency, and reversibility are core design principles.

---

## Status

This project is under active development.

Current focus:
- identity and orchestration
- safe local execution
- clean ingress paths (Telegram, CLI, future UI)

Behavior, skills, and integrations will evolve incrementally.
