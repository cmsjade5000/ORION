#!/usr/bin/env bash
set -euo pipefail

# Persist Morning Brief calendar configuration into ~/.openclaw/openclaw.json (env.vars).
#
# Usage:
#   ./scripts/morning_brief_set_calendars.sh --names "Work,Family,Birthdays" --window-hours 24 --include-allday 1
#
# This stores only non-secret preferences.

CFG="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"
NAMES=""
HOURS="24"
INCLUDE_ALLDAY="1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --names)
      NAMES="${2:-}"; shift 2 ;;
    --window-hours)
      HOURS="${2:-}"; shift 2 ;;
    --include-allday)
      INCLUDE_ALLDAY="${2:-}"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 --names \"A,B,C\" [--window-hours 24] [--include-allday 1]" >&2
      exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2 ;;
  esac
done

if [[ -z "${NAMES// /}" ]]; then
  echo "Missing --names" >&2
  exit 2
fi

if [[ ! -f "$CFG" ]]; then
  echo "OpenClaw config not found: $CFG" >&2
  exit 2
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Missing dependency: jq" >&2
  exit 2
fi

TMP="$(mktemp)"
cp -p "$CFG" "${CFG}.bak"

jq --arg names "$NAMES" --arg hours "$HOURS" --arg include "$INCLUDE_ALLDAY" '
  .env.vars = ((.env.vars // {}) + {
    BRIEF_CALENDAR_NAMES: $names,
    BRIEF_CALENDAR_WINDOW_HOURS: $hours,
    BRIEF_CALENDAR_INCLUDE_ALLDAY: $include
  })
' "$CFG" >"$TMP"

mv "$TMP" "$CFG"

echo "Updated ${CFG} env.vars:"
jq -r '.env.vars' "$CFG"
echo
echo "Restart required: openclaw gateway restart"

