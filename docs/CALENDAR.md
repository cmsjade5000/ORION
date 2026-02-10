# Calendar Integration (macOS Calendar.app)

This repo can include upcoming calendar events in the Morning Brief (email + voice).

## How It Works

- Fetcher: `scripts/calendar_events_fetch.sh`
  - Uses `osascript -l JavaScript` (JXA) to read Calendar.app events.
  - Outputs JSON and is consumed by `scripts/brief_inputs.sh`.
- Aggregator: `scripts/brief_inputs.sh` adds a `.calendar` object to the Morning Brief input JSON.
- Senders:
  - Email: `scripts/morning_debrief_send.sh`
  - Voice (Telegram): `scripts/morning_debrief_voice_send.sh`

## Configuration (Non-Secret)

These environment variables control which calendars are included:

- `BRIEF_CALENDAR_NAMES` (comma-separated calendar names)
- `BRIEF_CALENDAR_WINDOW_HOURS` (default: `24`) window from send time
- `BRIEF_CALENDAR_INCLUDE_ALLDAY` (`1` or `0`, default: `1`)

Recommended: persist them via OpenClaw config (`~/.openclaw/openclaw.json` `env.vars`):

```bash
./scripts/morning_brief_set_calendars.sh \
  --names "Work, Family, Birthdays" \
  --window-hours 24 \
  --include-allday 1
openclaw gateway restart
```

## Permissions (macOS Automation)

Calendar.app access may require macOS permission for automation (Apple Events).

If calendar events are missing or you see an automation error:

1. Run a manual probe to trigger the permission prompt:
   ```bash
   CAL_NAMES="Work" ./scripts/calendar_events_fetch.sh | head -c 200
   ```
2. Allow the request in macOS System Settings:
   - Privacy & Security
   - Automation
   - Allow the relevant tool (often `osascript`) to control Calendar

## Troubleshooting

- If `.calendar.enabled` is `true` but events are empty, it may simply mean you have no events in the next 24 hours.
- If `.calendar.error` is present, permissions are the first thing to check.

