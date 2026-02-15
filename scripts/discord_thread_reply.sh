#!/usr/bin/env bash
set -euo pipefail

# Reply inside an existing Discord thread via OpenClaw.
#
# Usage:
#   scripts/discord_thread_reply.sh <thread_target> <text...>
#   scripts/discord_thread_reply.sh <thread_target> -   # read message from stdin
#
# Notes:
# - Discord thread ids are channel ids; use `channel:<thread_id>` or the raw id.
#
# Env:
#   ORION_SUPPRESS_DISCORD / DISCORD_SUPPRESS  If truthy, do not send (exit 0).
#   OPENCLAW_BIN                           Optional absolute path override.

if [[ $# -lt 2 ]]; then
  echo "Usage: scripts/discord_thread_reply.sh <thread_target> <text...|->" >&2
  exit 2
fi

target="$1"
shift

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SUPPRESS_RAW="${ORION_SUPPRESS_DISCORD:-${DISCORD_SUPPRESS:-}}"
case "$(printf '%s' "${SUPPRESS_RAW}" | tr '[:upper:]' '[:lower:]')" in
  1|true|yes|y|on)
    echo "DISCORD_SUPPRESSED"
    exit 0
    ;;
esac

msg=""
if [[ "${1:-}" = "-" ]]; then
  msg="$(cat)"
else
  msg="$*"
fi

if ! printf '%s' "${msg}" | python3 "${SCRIPT_DIR}/discord_mass_mention_guard.py"; then
  exit 1
fi

OPENCLAW="${OPENCLAW_BIN:-}"
if [[ -z "${OPENCLAW}" ]]; then
  OPENCLAW="${SCRIPT_DIR}/openclaww.sh"
fi

exec "${OPENCLAW}" message thread reply --channel discord --target "${target}" --message "${msg}"
