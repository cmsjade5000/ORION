#!/usr/bin/env bash
set -euo pipefail

# Create a Discord thread in a given channel via OpenClaw.
#
# Usage:
#   scripts/discord_thread_create.sh <channel_target> <thread_name> [initial_message...]
#
# Example:
#   scripts/discord_thread_create.sh channel:123 "task: gateway triage" "Start thread"
#
# Env:
#   ORION_SUPPRESS_DISCORD / DISCORD_SUPPRESS  If truthy, do not send (exit 0).
#   OPENCLAW_BIN                           Optional absolute path override.

if [[ $# -lt 2 ]]; then
  echo "Usage: scripts/discord_thread_create.sh <channel_target> <thread_name> [initial_message...]" >&2
  exit 2
fi

target="$1"
thread_name="$2"
shift 2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SUPPRESS_RAW="${ORION_SUPPRESS_DISCORD:-${DISCORD_SUPPRESS:-}}"
case "$(printf '%s' "${SUPPRESS_RAW}" | tr '[:upper:]' '[:lower:]')" in
  1|true|yes|y|on)
    echo "DISCORD_SUPPRESSED"
    exit 0
    ;;
esac

initial_msg="${*:-}"
if [[ -n "${initial_msg}" ]]; then
  if ! printf '%s' "${initial_msg}" | python3 "${SCRIPT_DIR}/discord_mass_mention_guard.py"; then
    exit 1
  fi
fi

OPENCLAW="${OPENCLAW_BIN:-}"
if [[ -z "${OPENCLAW}" ]]; then
  OPENCLAW="${SCRIPT_DIR}/openclaww.sh"
fi

args=(message thread create --channel discord --target "${target}" --thread-name "${thread_name}")
if [[ -n "${initial_msg}" ]]; then
  args+=(--message "${initial_msg}")
fi

exec "${OPENCLAW}" "${args[@]}"
