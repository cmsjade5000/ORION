#!/usr/bin/env bash
set -euo pipefail

# Install bounded-proactive assistant crons after Telegram inbound has been verified.
# Safe default: print commands unless --apply is passed.

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
APPLY=0
if [[ "${2:-}" == "--apply" || "${1:-}" == "--apply" ]]; then
  APPLY=1
fi

if ! command -v openclaw >/dev/null 2>&1; then
  echo "openclaw is required" >&2
  exit 2
fi

read -r -d '' CMD1 <<'EOF' || true
openclaw cron add \
  --name "assistant-agenda-refresh" \
  --description "Refresh ORION assistant agenda artifact" \
  --cron "*/15 * * * *" \
  --tz "America/New_York" \
  --no-deliver \
  --agent main \
  --session isolated \
  --message "Use system.run to execute exactly: python3 scripts/assistant_status.py --cmd refresh --json. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."
EOF

read -r -d '' CMD2 <<'EOF' || true
openclaw cron add \
  --name "assistant-inbox-notify" \
  --description "Notify Cory when assistant packets complete" \
  --cron "*/2 * * * *" \
  --tz "America/New_York" \
  --no-deliver \
  --agent main \
  --session isolated \
  --message "Use system.run to execute exactly: python3 scripts/notify_inbox_results.py --require-notify-telegram. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."
EOF

read -r -d '' CMD3 <<'EOF' || true
openclaw cron add \
  --name "assistant-task-loop" \
  --description "Reconcile assistant tickets and fail loudly on stale admin work" \
  --cron "*/5 * * * *" \
  --tz "America/New_York" \
  --no-deliver \
  --agent main \
  --session isolated \
  --message "Use system.run to execute exactly: python3 scripts/task_execution_loop.py --apply --strict-stale --stale-hours 24. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."
EOF

for cmd in "$CMD1" "$CMD2" "$CMD3"; do
  if [[ "$APPLY" -eq 1 ]]; then
    eval "$cmd"
  else
    printf '%s\n\n' "$cmd"
  fi
done
