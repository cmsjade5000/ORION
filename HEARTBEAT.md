# Heartbeat (OpenClaw-Compatible)

This file is intended to be used by OpenClaw's heartbeat runner. Keep it cheap.

## Principles

- Human messages first.
- Do not burn tokens "just to be busy".
- In current single-bot mode, only ORION may message Cory via Telegram.

## Step 1: Triage (fast)

1. Check `tasks/QUEUE.md`.
2. Check `tasks/INBOX/` for any newly completed Task Packets (look for `Result:` blocks).
3. If there is a clear Ready task that is safe and bounded, pick exactly one.
4. If anything is ambiguous, risky, or needs confirmation, stop and ask Cory.

## Step 2: Execute (bounded)

If you picked a task:

Default policy: **triage-only**. Do not modify the repo during heartbeat runs.

You may only execute work during a heartbeat if Cory has explicitly marked the item as safe for unattended automation, for example with a tag like `AUTO_OK`, and the work is small + reversible.

If a Ready task exists but is not explicitly automation-approved:

1. Notify Cory (Slack `#projects` preferred) with a 1–3 bullet summary and ask for confirmation.
2. Then stop and output `HEARTBEAT_OK`.

## Step 3: Idle Behavior

If there is no urgent work and no Ready task you can safely execute:

- Output exactly: `HEARTBEAT_OK`
