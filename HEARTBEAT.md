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

1. Mark it as in progress with `@orion: ...` in `tasks/QUEUE.md`.
2. Do the smallest useful unit of work.
3. Update `tasks/QUEUE.md` and write a short note in `memory/WORKING.md` if anything meaningful changed.

## Step 3: Idle Behavior

If there is no urgent work and no Ready task you can safely execute:

- Output exactly: `HEARTBEAT_OK`
