# Follow-Through (Stop Needing "Continue")

Problem: ORION can delegate multi-step work to specialists, but results may land asynchronously (for example in `tasks/INBOX/*.md`). If nothing triggers a user-facing follow-up, Cory ends up prodding ORION with “continue” messages.

Goal: when a delegated packet completes, Cory gets a short Telegram or Discord update automatically.

## Mechanism (Single-Bot Mode)

1. ORION creates a Task Packet in `tasks/INBOX/<AGENT>.md` and includes:
   - `Notify: telegram` or `Notify: discord` (or `Notify: telegram,discord`)
2. The specialist writes a `Result:` block under that packet when done.
3. A periodic run executes:
   - `python3 scripts/notify_inbox_results.py --require-notify-telegram` (Telegram)
   - `python3 scripts/notify_inbox_results.py --require-notify-discord` (Discord)
4. The notifier sends a concise update and remembers what it already notified (state in `tmp/inbox_notify_state.json`).

Notes:
- The notifier is bounded and non-spammy (default max 3 results per run).
- Heartbeat outputs remain `NO_REPLY`; the script does the send.
  - Telegram: direct API call (token file or env var).
  - Discord: uses `openclaw message send --channel discord ...` (so this script never touches the Discord token).

## Recommended Packet Result Format

Specialists should add, under the packet:

```text
Result:
- Status: OK | FAILED | BLOCKED
- What changed / what I found:
- Next step (if any):
```

Keep it short; avoid tool logs and secrets.

## Cron (Recommended)

Add a lightweight cron that runs every 2 minutes:

```bash
openclaw cron add \
  --name "inbox-result-notify" \
  --description "Notify Cory when Notify: telegram inbox packets get Result blocks" \
  --cron "*/2 * * * *" \
  --tz "America/New_York" \
  --agent main \
  --session isolated \
  --message "Run python3 scripts/notify_inbox_results.py --require-notify-telegram. Respond NO_REPLY."

Discord variant (set a default target first):

```bash
export DISCORD_DEFAULT_POST_TARGET="user:<CORY_DISCORD_USER_ID>"
openclaw cron add \
  --name "inbox-result-notify-discord" \
  --description "Notify Cory on Discord when Notify: discord inbox packets get Result blocks" \
  --cron "*/2 * * * *" \
  --tz "America/New_York" \
  --agent main \
  --session isolated \
  --message "Run python3 scripts/notify_inbox_results.py --require-notify-discord. Respond NO_REPLY."
```
```

## Dry-Run / Testing

This prints what it would send and does not require Telegram/Discord credentials:

```bash
NOTIFY_DRY_RUN=1 python3 scripts/notify_inbox_results.py --require-notify-telegram
```

You can also suppress sends (while still writing notifier state and emitting Mini App events):

```bash
ORION_SUPPRESS_TELEGRAM=1 python3 scripts/notify_inbox_results.py --require-notify-telegram
```

```bash
ORION_SUPPRESS_DISCORD=1 DISCORD_DEFAULT_POST_TARGET="user:<CORY_DISCORD_USER_ID>" \
  python3 scripts/notify_inbox_results.py --require-notify-discord
```
