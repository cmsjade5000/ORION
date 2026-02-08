---
name: slack-handbook
description: ORION's field manual for operating in Slack (channels, threads, search, safe posting) plus OpenClaw CLI snippets for navigation.
metadata:
  invocation: user
---

# Slack Handbook (ORION)

Use this skill when you need to operate inside Slack reliably: choosing where to post, staying in threads, finding channel IDs, and avoiding spam/mentions.

Canonical local guide:
- `docs/SLACK_OPERATOR_GUIDE.md`

## Rules (ORION)

- Prefer channels for durable work context; prefer threads for replies.
- Keep messages short and scannable.
- Do not use `@channel` / `@here` unless Cory explicitly asks.
- Specialists never post to Slack; only ORION does. Prefix specialist outputs with `[AGENT]`.

## Navigation Helpers (OpenClaw CLI via exec)

Resolve channel IDs (when needed):

```bash
openclaw channels resolve --channel slack "#projects" --json
```

Read recent messages:

```bash
openclaw message read --channel slack --target "#projects" --limit 20 --json
```

Send message (channel):

```bash
openclaw message send --channel slack --target "#projects" --message "..."
```

Send message (thread, when you have a thread id):

```bash
openclaw message send --channel slack --target "#projects" --message "..." --thread-id "<thread_id>"
```

## When You’re Unsure

- If you don’t know the right channel: ask Cory once ("#projects or #general?").
- If you don’t know whether to reply in-thread: default to in-thread.
- If you don’t have enough context: read the last 20 messages from the channel first.
