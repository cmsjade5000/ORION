#!/usr/bin/env bash
set -euo pipefail

# Convenience helper: send yourself (the allowlisted Telegram user) an inline `web_app`
# button to open the Mini App dashboard.
#
# This uses:
# - chat id from ~/.openclaw/openclaw.json (channels.telegram.allowFrom[0])
# - URL from env ORION_MINIAPP_URL or ~/.openclaw/openclaw.json (env.vars.ORION_MINIAPP_URL)
#
# Usage:
#   ./scripts/telegram_open_miniapp.sh [url_override]

CFG="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"
URL_OVERRIDE="${1:-}"

if [[ ! -f "${CFG}" ]]; then
  echo "OpenClaw config not found: ${CFG}" >&2
  exit 2
fi

CHAT_ID="$(jq -r '.channels.telegram.allowFrom[0] // empty' "${CFG}")"
if [[ -z "${CHAT_ID}" || "${CHAT_ID}" == "null" ]]; then
  echo "Could not determine Telegram chat id from ${CFG} (channels.telegram.allowFrom[0])." >&2
  exit 2
fi

URL="${URL_OVERRIDE:-${ORION_MINIAPP_URL:-}}"
if [[ -z "${URL}" ]]; then
  URL="$(jq -r '.env.vars.ORION_MINIAPP_URL // empty' "${CFG}")"
fi

if [[ -z "${URL}" || "${URL}" == "null" ]]; then
  echo "Missing ORION_MINIAPP_URL. Set env ORION_MINIAPP_URL or configure env.vars.ORION_MINIAPP_URL in ${CFG}." >&2
  exit 2
fi

exec /Users/corystoner/Desktop/ORION/scripts/telegram_send_miniapp_button.sh "${CHAT_ID}" "${URL}"

