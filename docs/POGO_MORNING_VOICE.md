# Pokemon GO Morning Voice (Shiny-First, 60 Seconds)

Owner: ORION (Telegram)

Goal:
- Deliver a daily 60-second in-universe Pokemon GO briefing, optimized for shiny hunting.

## What This Version Implements

- 60-second voice-first briefing (`scripts/pogo_morning_voice_send.sh`)
- Official-source parsing from:
  - `https://pokemongo.com/en/news/`
  - `https://pokemongo.com/en/events/`
- Stale-data confidence guard (`high`/`medium`/`low`)
- Commute check against work shifts:
  - Any event with `R096` in title under configured work calendars is treated as a work shift
- Urgency tiers (`low|medium|high`) mapped to TTS presets
- Weekly story arc line (Monday-Sunday)
- Telegram text command scaffolding:
  - `/pogo_help`
  - `/pogo_voice`
  - `/pogo_text`
  - `/pogo_today`
  - `/pogo_status`
- Metrics scaffolding (JSONL logging; heavy analytics deferred)

## Required Secrets

- `~/.openclaw/secrets/telegram.token`
- `~/.openclaw/secrets/elevenlabs.api_key`

## Recommended Config (OpenClaw env.vars)

- `POGO_CALENDAR_NAMES` (comma-separated calendars to scan)
- `POGO_WORK_CALENDAR_NAMES` (work-only calendars)
- `POGO_COMMUTE_KEYWORDS` (defaults include `commute,drive,train,bus,subway,uber,lyft`)
- `POGO_TZ` (default `America/New_York`)
- `POGO_STALE_NEWS_HOURS` (default `120`)

## Manual Checks

Dry-run (build input + synthesize voice only):

```bash
./scripts/pogo_morning_voice_send.sh
```

Send now:

```bash
./scripts/pogo_morning_voice_send.sh --send
```

Prompt-only ask (voice vs text):

```bash
./scripts/pogo_morning_voice_send.sh --send --prompt-only
```

Text-only send fallback:

```bash
./scripts/pogo_morning_voice_send.sh --send --text-only
```

## Suggested Cron (Not Applied Automatically)

```bash
openclaw cron add \
  --name "pogo-morning-voice" \
  --description "Ask delivery mode, then send Pokemon GO shiny-first 60s brief" \
  --cron "0 9 * * 1-5" \
  --tz "America/New_York" \
  --agent main \
  --session isolated \
  --message "Run scripts/pogo_morning_voice_send.sh --send --prompt-only. Respond NO_REPLY."
```

## Notes

- This pipeline avoids unofficial scraping dependencies and uses official Pokemon GO site pages.
- Metrics aggregation and personalization beyond shiny-first behavior are intentionally scaffolded for later.
