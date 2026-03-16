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

legacy_names=(
  "assistant-agenda-refresh"
  "assistant-inbox-notify"
  "inbox-result-notify"
  "assistant-task-loop"
  "orion-error-review"
  "orion-session-maintenance"
)

remove_matching_jobs() {
  local jobs_json ids
  jobs_json="$(openclaw cron list --json)"
  ids="$(
    python3 - "$jobs_json" "${legacy_names[@]}" <<'PY'
import json
import sys

raw = sys.argv[1]
start = raw.find("{")
if start < 0:
    raise SystemExit(0)
payload = json.loads(raw[start:])
names = set(sys.argv[2:])
for job in payload.get("jobs", []):
    if job.get("name") in names and job.get("id"):
        print(job["id"])
PY
  )"

  while IFS= read -r job_id; do
    [[ -z "${job_id}" ]] && continue
    if [[ "$APPLY" -eq 1 ]]; then
      openclaw cron rm --json "${job_id}" >/dev/null
    else
      printf 'openclaw cron rm --json %s\n\n' "${job_id}"
    fi
  done <<< "${ids}"
}

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

read -r -d '' CMD4 <<'EOF' || true
openclaw cron add \
  --name "orion-error-review" \
  --description "Review recurring ORION errors and apply safe remediations" \
  --cron "15 2 * * *" \
  --tz "America/New_York" \
  --no-deliver \
  --agent main \
  --session isolated \
  --message "Use system.run to execute exactly: python3 scripts/orion_error_db.py --repo-root . review --window-hours 24 --apply-safe-fixes --escalate-incidents --json. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."
EOF

read -r -d '' CMD5 <<'EOF' || true
openclaw cron add \
  --name "orion-session-maintenance" \
  --description "Prune stale ORION session metadata when drift exceeds threshold" \
  --cron "45 2 * * *" \
  --tz "America/New_York" \
  --no-deliver \
  --agent main \
  --session isolated \
  --message "Use system.run to execute exactly: AUTO_OK=1 python3 scripts/session_maintenance.py --repo-root . --agent main --fix-missing --apply --doctor --min-missing 50 --min-reclaim 25 --json. Ignore stdout/stderr unless it fails. Then respond exactly NO_REPLY."
EOF

remove_matching_jobs

for cmd in "$CMD1" "$CMD2" "$CMD3" "$CMD4" "$CMD5"; do
  if [[ "$APPLY" -eq 1 ]]; then
    eval "$cmd"
  else
    printf '%s\n\n' "$cmd"
  fi
done
