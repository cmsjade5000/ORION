#!/usr/bin/env bash
set -euo pipefail

# Send a plain Discord message using OpenClaw's Discord channel plugin.
#
# Usage:
#   scripts/discord_send_message.sh <target> <text...>
#   scripts/discord_send_message.sh <target> -   # read message from stdin
#
# Target examples:
#   user:123456789012345678
#   channel:123456789012345678
#   123456789012345678     # auto
#
# Env:
#   ORION_SUPPRESS_DISCORD / DISCORD_SUPPRESS  If truthy, do not send (exit 0).
#   OPENCLAW_BIN                           Optional absolute path override.

if [[ $# -lt 2 ]]; then
  echo "Usage: scripts/discord_send_message.sh <target> <text...|->" >&2
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

exec "${OPENCLAW}" message send --channel discord --target "${target}" --message "${msg}"
