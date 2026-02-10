#!/usr/bin/env bash
set -euo pipefail

# List macOS Calendar.app calendar names (one per line).
#
# Usage:
#   ./scripts/calendar_list.sh

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: calendar_list is macOS-only (Calendar.app)." >&2
  exit 2
fi

osascript -e '
tell application "Calendar"
  set out to ""
  repeat with c in calendars
    set out to out & (name of c as text) & linefeed
  end repeat
  return out
end tell
' | sed '/^[[:space:]]*$/d'

