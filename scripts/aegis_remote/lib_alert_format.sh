#!/usr/bin/env bash

# Shared alert formatting for AEGIS/ORION-style messages.
# Keep this consistent with docs/ALERT_FORMAT.md.

format_alert() {
  # format_alert <title> <what_saw> [what_did] [next] [incident]
  local title="${1-}"
  local what_saw="${2-}"
  local what_did="${3-}"
  local next="${4-}"
  local incident="${5-}"

  printf '%s' "$title"

  if [ -n "$what_saw" ] || [ -n "$what_did" ] || [ -n "$next" ] || [ -n "$incident" ]; then
    printf '\n\n'
  fi

  if [ -n "$what_saw" ]; then
    printf 'What I saw: %s\n' "$what_saw"
  fi
  if [ -n "$what_did" ]; then
    printf 'What I did: %s\n' "$what_did"
  fi
  if [ -n "$next" ]; then
    printf 'Next: %s\n' "$next"
  fi
  if [ -n "$incident" ]; then
    printf 'Incident: %s\n' "$incident"
  fi
}

