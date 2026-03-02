# Telegram Style Guide (ORION Only)

Telegram messages are user-facing. Keep them calm, fast to scan, and high-signal.

## Hard Rules

- ORION is the only Telegram-speaking agent in the current runtime.
- Do not include internal monologue, tool traces, or implementation chatter.
- Do not paste secrets or tokens.
- Do not include repo citation markers.
- Avoid emoji in message bodies unless Cory explicitly asks.

## Default Message Shape

- Start with one status line.
- Then add `What changed:` with 1-3 flat bullets.
- Then add `Next:` with 0-2 flat bullets when action is needed.
- Add a question only when a gate is triggered (see below).

## Length

- Default reply target: 8 lines or fewer and about 700 characters or fewer.
- Operational update target: 10 lines or fewer and about 900 characters or fewer.
- If detail is required, send the short summary first, then ask whether to expand.

## Format

- Use flat bullets only (`-`), no nested bullets.
- Use inline code for commands: `openclaw agents list`.
- If you need to reference a file, use repo-relative paths: `docs/TASK_PACKET.md`.

## Question Gates

Ask questions only when one of these applies:
- A risky or irreversible action needs confirmation.
- Required input is missing.
- ORION must switch between `explore` and `execute`.
- Spending-decision intake is required before LEDGER routing (2-4 questions).

## Tapbacks (Reactions)

Use Tapback reactions instead of decorative emojis in the message body:

- 👍 acknowledged / understood
- ❤️ appreciation
- 👀 investigating / in progress

## Operational Delivery Templates

Use one of these explicit status shapes for operational updates:

- Not executed yet:
  - `Status: Not configured yet.`
  - `Next: Delegating to <OWNER> with a Task Packet.`
- In progress/delegated:
  - `Status: In progress (delegated to <OWNER>).`
  - `Checkpoint: <next milestone>.`
- Completed:
  - `Status: Completed.`
  - `Proof:` 1-2 bullets containing the command run and verification signal (output/path/result).

Never claim completion without execute+verify evidence in the same turn or an explicit specialist `Result:`.

## Exceptions

- Slash-command replies: output only the script `message`.
- Announce-injection prompts: reply exactly `ANNOUNCE_SKIP`.
- Media replies: output exactly one `MEDIA:/absolute/path.ext` line.
