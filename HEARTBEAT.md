# Heartbeat (OpenClaw-Compatible)

This file is intended to be used by OpenClaw's heartbeat runner. Keep it cheap.

## Principles

- Human messages first.
- Do not burn tokens "just to be busy".
- In current single-bot mode, only ORION may message Cory via Telegram.
- Heartbeats are **silent**: do not post to Slack/Telegram/email during heartbeat runs.
  - If something needs attention, log it (see below) and wait for Cory to ask.
- Always output exactly `NO_REPLY` so OpenClaw does not post a heartbeat message to Slack.

## Step 1: Triage (fast)

1. Check `tasks/QUEUE.md`.
2. Check the per-agent inbox *files* for any newly completed Task Packets (look for `Result:` blocks):
   - `tasks/INBOX/ATLAS.md`
   - `tasks/INBOX/NODE.md`
   - `tasks/INBOX/PULSE.md`
   - `tasks/INBOX/STRATUS.md`
   - `tasks/INBOX/WIRE.md`
   - `tasks/INBOX/SCRIBE.md`
   - `tasks/INBOX/PIXEL.md`
   - `tasks/INBOX/EMBER.md`
   - `tasks/INBOX/LEDGER.md`
   - Do not `read` the `tasks/INBOX/` directory path directly (it triggers EISDIR errors).
3. If there is a clear Ready task that is safe and bounded, pick exactly one.
4. If anything is ambiguous, risky, or needs confirmation, stop and ask Cory.

## Step 2: Execute (bounded)

If you picked a task:

Default policy: **triage-only**. Do not modify the repo during heartbeat runs.

You may only execute work during a heartbeat if Cory has explicitly marked the item as safe for unattended automation, for example with a tag like `AUTO_OK`, and the work is small + reversible.

If a Ready task exists but is not explicitly automation-approved:

1. Do not notify any channel.
2. Log one line to `tmp/heartbeat.log` (timestamp + short summary).
3. Then stop and output exactly: `NO_REPLY`.

## Step 3: Idle Behavior

If there is no urgent work and no Ready task you can safely execute:

- Log one line to `tmp/heartbeat.log` (timestamp + `idle`).
- Output exactly: `NO_REPLY`
