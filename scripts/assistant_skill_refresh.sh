#!/usr/bin/env bash
set -euo pipefail

# Monthly maintenance helper for assistant-oriented skill hygiene.
# Safe default: generate a durable review artifact and print the update command
# unless --apply is passed.

APPLY=0
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=1
fi

report_cmd='python3 scripts/clawhub_skill_refresh.py --output-json tmp/clawhub_skill_refresh_latest.json --output-md tmp/clawhub_skill_refresh_latest.md'
update_cmd='openclaw skills update --all'
discovery_cmd='python3 scripts/skill_discovery_scan.py --limit 8'

eval "$report_cmd"
eval "$discovery_cmd"

if [[ "$APPLY" -eq 1 ]]; then
  python3 scripts/skill_discovery_scan.py --limit 8 --update-shortlist
  eval "$update_cmd"
else
  printf '%s\n' "$update_cmd"
fi
