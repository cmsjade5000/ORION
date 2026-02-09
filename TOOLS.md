# Tools

This document defines how tools may be used within the Gateway system.

It does not enumerate every available tool.
It defines constraints, responsibility, and safe usage patterns.

---

## Tool Philosophy

Tools exist to support Cory’s intent.
They are never used autonomously, speculatively, or without context.

Prefer:
- small, reversible actions
- explicit confirmation for risk
- clarity over cleverness

---

## Tool Ownership

- ORION orchestrates tool usage decisions.
- ATLAS executes approved operational tools.
- NODE reviews architectural or systemic implications.
- WIRE performs sources-first retrieval (links/evidence) and returns results to ORION only (internal-only).
- Other agents may recommend tools but do not invoke them.

Email tools:
- ORION is the only agent allowed to use email integrations.
- Specialists are email-blind.
- Default: send immediately for explicit user commands (unless the user says “draft only”).
- Autonomous sending is allowed only for explicitly approved automations (for example the Morning Brief).

---

## Execution Rules

- Destructive commands require explicit user approval.
- Network exposure, credential changes, or system modifications must be surfaced clearly before execution.
- Enabling Mini App command routing into ORION (`OPENCLAW_ROUTE_COMMANDS=1` in `apps/telegram-miniapp-dashboard/`) is treated as a system modification and requires explicit approval.
- Prefer dry-runs, previews, or explanations before acting.
- Prefer routing operational execution through ATLAS (ORION -> ATLAS -> (NODE|PULSE|STRATUS)) unless the action is a deterministic local script (for example a verified AgentMail send wrapper).

---

## Git & Filesystem

- Git is the primary change-tracking mechanism.
- Prefer small, atomic commits.
- Never modify files in `keep/`.
- Generated files (e.g. `agents/*/SOUL.md`) should not be edited by hand.

---

## Secrets & Credentials

- Secrets are never stored in plaintext.
- Secrets are never echoed back in logs or output.
- Access to secrets follows `KEEP.md`.

---

## What Is Not Allowed

- Running background daemons without approval
- Self-modifying system behavior
- Tool use that bypasses SECURITY.md constraints
- Assumptions about permissions not explicitly granted
