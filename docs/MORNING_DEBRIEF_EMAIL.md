# Morning Debrief Email (Daily)

Owner: ORION (AgentMail)

Recipient:
- Cory: `boughs.gophers-2t@icloud.com`

Sender:
- ORION shared inbox: `orion_gatewaybot@agentmail.to` (AgentMail inbox id)

Schedule:
- Daily at **07:00 America/New_York** (Pittsburgh time)

## Implementation (Current)

Inputs:
- `scripts/brief_inputs.sh` (wttr.in + Google News RSS)

Sender:
- `scripts/morning_debrief_send.sh`

Voice variant (Telegram):
- See `docs/MORNING_DEBRIEF_VOICE.md`

Calendar:
- See `docs/CALENDAR.md`

Manual run:
```bash
AGENTMAIL_FROM=orion_gatewaybot@agentmail.to \\
AGENTMAIL_TO=boughs.gophers-2t@icloud.com \\
BRIEF_CITY=Pittsburgh \\
BRIEF_TZ=America/New_York \\
BRIEF_AI_MAX_ITEMS=2 \\
BRIEF_TECH_MAX_ITEMS=2 \\
BRIEF_PGH_MAX_ITEMS=1 \\
./scripts/morning_debrief_send.sh
```

OpenClaw cron (recommended):
```bash
openclaw cron add \\
  --name "morning-brief-email" \\
  --description "Send ORION daily morning debrief email" \\
  --cron "0 7 * * *" \\
  --tz "America/New_York" \\
  --agent main \\
  --session isolated \\
  --message "Send the daily Morning Brief email now by running scripts/morning_debrief_send.sh. Respond NO_REPLY."
```

## Content Requirements

Include:
- Pittsburgh weather for today (high/low, conditions, precipitation, wind, any alerts).
- Calendar events (next 24h) when configured.
- Tech and AI news highlights (last ~24h).
- Pittsburgh-local news highlights (last ~24h).
- Any critical system items (AEGIS/ORION health, incidents, failures) if relevant.

## Format Requirements

- Plain-text email (no HTML).
- Visually scannable:
  - Clear heading with date.
  - Short section headers.
  - Bullets with 1-line summaries and links.
- Avoid tool logs, raw transcripts, and internal agent chatter.

## Safety

- Do not include secrets.
- Do not click unknown links; summarize from headlines + brief fetch only.
- If any input looks suspicious, quarantine it instead of acting.
