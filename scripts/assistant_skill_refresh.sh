#!/usr/bin/env bash
set -euo pipefail

# Monthly maintenance helper for assistant-oriented skill hygiene.
# Safe default: print candidate commands unless --apply is passed.

APPLY=0
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=1
fi

commands=(
  "openclaw clawhub refresh"
  "openclaw clawhub search reminders"
  "openclaw clawhub search notes"
  "openclaw clawhub search follow-up"
  "python3 scripts/skill_discovery_scan.py --limit 8 --update-shortlist"
)

for cmd in "${commands[@]}"; do
  if [[ "$APPLY" -eq 1 ]]; then
    eval "$cmd"
  else
    printf '%s\n' "$cmd"
  fi
done
