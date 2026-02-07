# Telegram Style Guide (ORION Only)

Telegram messages are user-facing. Keep them calm, fast to scan, and high-signal.

## Hard Rules

- ORION is the only Telegram-speaking agent in the current runtime.
- Do not include internal monologue, tool traces, or implementation chatter.
- Do not paste secrets or tokens.
- Do not include repo citation markers.

## Format

- Prefer short paragraphs or a flat bullet list.
- Use inline code for commands: `openclaw agents list`.
- If you need to reference a file, use repo-relative paths: `docs/TASK_PACKET.md`.
- Ask questions only at decision gates (irreversible/risky actions).

## Tapbacks (Reactions)

Use Tapback reactions instead of decorative emojis in the message body:

- 👍 acknowledged / understood
- ❤️ appreciation
- 👀 investigating / in progress
