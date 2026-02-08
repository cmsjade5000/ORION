#!/usr/bin/env bash
set -euo pipefail

# Append an INCIDENT v1 entry to tasks/INCIDENTS.md.
#
# This is intentionally simple: it reduces formatting drift and prevents
# accidental inclusion of secrets/tool logs in incident writeups.
#
# Usage:
#   scripts/incident_append.sh \
#     --opened-by ORION \
#     --severity P1 \
#     --trigger ORION_GATEWAY_RESTART \
#     --summary "Restarted gateway after config reload" \
#     --evidence "gateway.err.log shows AbortError spam" \
#     --action "openclaw gateway restart" \
#     --follow-up-owner ATLAS \
#     --follow-up "Review restart cause + add guard" \
#     --closed open
#
# Notes:
# - Keep strings short; do not paste tokens, keys, full tool logs, or stack traces.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INCIDENTS_FILE="$ROOT_DIR/tasks/INCIDENTS.md"

usage() {
  cat <<'TXT' >&2
Usage:
  incident_append.sh --opened-by <ORION|AEGIS> --severity <P0|P1|P2> --trigger <TRIGGER> --summary <TEXT> [options]

Options:
  --id <ID>                   Optional incident id (default: generated)
  --opened-by <NAME>          ORION | AEGIS
  --severity <P0|P1|P2>
  --trigger <TRIGGER>
  --summary <TEXT>
  --evidence <TEXT>           May be provided multiple times
  --action <TEXT>             May be provided multiple times
  --follow-up-owner <NAME>    ORION | ATLAS | Cory (default: ORION)
  --follow-up <TEXT>          May be provided multiple times
  --closed <ISO|open>         Default: open
TXT
  exit 2
}

id=""
opened_by=""
severity=""
trigger=""
summary=""
follow_owner="ORION"
closed="open"
evidence=()
actions=()
followups=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --id) id="${2-}"; shift 2 ;;
    --opened-by) opened_by="${2-}"; shift 2 ;;
    --severity) severity="${2-}"; shift 2 ;;
    --trigger) trigger="${2-}"; shift 2 ;;
    --summary) summary="${2-}"; shift 2 ;;
    --evidence) evidence+=("${2-}"); shift 2 ;;
    --action) actions+=("${2-}"); shift 2 ;;
    --follow-up-owner) follow_owner="${2-}"; shift 2 ;;
    --follow-up) followups+=("${2-}"); shift 2 ;;
    --closed) closed="${2-}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

[[ -n "$opened_by" ]] || usage
[[ -n "$severity" ]] || usage
[[ -n "$trigger" ]] || usage
[[ -n "$summary" ]] || usage

case "$severity" in P0|P1|P2) ;; *) echo "Invalid --severity: $severity" >&2; exit 2 ;; esac

now="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
short_date="$(date -u '+%Y%m%d')"
short_time="$(date -u '+%H%M')"

if [[ -z "$id" ]]; then
  # Keep ids short + greppable.
  slug="$(printf '%s' "$trigger" | tr '[:upper:]' '[:lower:]' | tr '_' '-' | cut -c1-20)"
  id="INC-${short_date}-${short_time}-${slug}"
fi

mkdir -p "$(dirname "$INCIDENTS_FILE")"
touch "$INCIDENTS_FILE"

{
  printf '\n'
  printf 'INCIDENT v1\n'
  printf 'Id: %s\n' "$id"
  printf 'Opened: %s\n' "$now"
  printf 'Opened By: %s\n' "$opened_by"
  printf 'Severity: %s\n' "$severity"
  printf 'Trigger: %s\n' "$trigger"
  printf 'Summary: %s\n' "$summary"
  printf 'Evidence:\n'
  if [[ ${#evidence[@]} -eq 0 ]]; then
    printf -- '- (none)\n'
  else
    for x in "${evidence[@]}"; do
      printf -- '- %s\n' "$x"
    done
  fi
  printf 'Actions:\n'
  if [[ ${#actions[@]} -eq 0 ]]; then
    printf -- '- (none)\n'
  else
    for x in "${actions[@]}"; do
      printf -- '- %s\n' "$x"
    done
  fi
  printf 'Follow-up Owner: %s\n' "$follow_owner"
  printf 'Follow-up Tasks:\n'
  if [[ ${#followups[@]} -eq 0 ]]; then
    printf -- '- (none)\n'
  else
    for x in "${followups[@]}"; do
      printf -- '- %s\n' "$x"
    done
  fi
  printf 'Closed: %s\n' "$closed"
} >>"$INCIDENTS_FILE"

echo "INCIDENT_APPENDED_OK id=$id file=$INCIDENTS_FILE"

