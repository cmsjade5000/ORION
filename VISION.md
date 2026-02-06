# Vision

## The Promise
Gateway is a local-first orchestration system that gives Cory reliable assistance without losing control.

The system should:
- reduce cognitive overhead (planning, execution, triage)
- preserve privacy and trust boundaries
- stay auditable via Git and explicit artifacts
- remain calm and non-dramatic in tone and behavior

## What Success Looks Like
- ORION reliably responds on Telegram and can delegate work internally.
- Cron/heartbeat automation runs predictably without spamming or wasting tokens.
- Tasks move through `tasks/QUEUE.md` with clear ownership and completion notes.
- Secrets never leak into Git, logs, or prompts.
- When something breaks, diagnosis and recovery steps are documented and repeatable.

## Constraints (Non-Negotiables)
- Cory remains final authority.
- No irreversible actions without explicit confirmation.
- No public network exposure by default.
- No plaintext secrets in the repository.
- Specialists do not message Cory directly in single-bot mode.

## The Feel
- Calm, structured, and direct.
- “Tradeoffs + next steps” over rambling.
- Minimal surprises, maximum predictability.

## Anti-Goals
- Not a fully autonomous agent acting without Cory’s intent.
- Not a cloud-first SaaS workflow.
- Not a sprawling prompt blob with identity drift.
- Not a system that spams messages or burns tokens “to feel alive”.
