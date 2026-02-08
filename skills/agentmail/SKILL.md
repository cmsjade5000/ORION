---
name: agentmail
description: ORION-only email send/receive via AgentMail (API). Specialists are email-blind by policy.
metadata:
  invocation: user
  openclaw:
    emoji: "📧"
    # This skill supports file-backed secrets (recommended), so we do not
    # hard-require an env var. If no key is available at runtime, the skill
    # will error with a clear message.
---

# AgentMail (ORION Only)

This skill provides programmatic access to the ORION shared inbox using AgentMail.

Policy:
- ORION may use this skill.
- Specialists must not call AgentMail APIs or handle raw email content.

## Setup (Local Secrets Only)

Provide an API key via either:
- `AGENTMAIL_API_KEY` environment variable, or
- `~/.openclaw/secrets/agentmail.api_key` (recommended).

Example:

```bash
mkdir -p ~/.openclaw/secrets
chmod 700 ~/.openclaw/secrets
printf "%s\n" "$AGENTMAIL_API_KEY" > ~/.openclaw/secrets/agentmail.api_key
chmod 600 ~/.openclaw/secrets/agentmail.api_key
```

## Quick Test

```bash
node -e "require('./skills/agentmail/manifest').listInboxes().then(console.log)"
```

## Common Operations

List inboxes:

```bash
node -e "require('./skills/agentmail/manifest').listInboxes().then(console.log)"
```

Create an inbox (optional):

```bash
node -e "require('./skills/agentmail/manifest').createInbox({displayName:'ORION Shared Inbox'}).then(console.log)"
```

List messages:

```bash
node -e "require('./skills/agentmail/manifest').listMessages(process.env.INBOX_ID,{limit:10}).then(console.log)"
```

Send email:

```bash
node -e \"require('./skills/agentmail/manifest').sendMessage(process.env.INBOX_ID,{to:'you@example.com',subject:'Test',text:'Hello from ORION'}).then(console.log)\"
```
