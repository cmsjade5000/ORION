#!/usr/bin/env bash
set -euo pipefail

# Send a Telegram inline keyboard button that opens the ORION Mini App (web_app).
#
# Usage:
#   scripts/telegram_send_miniapp_button.sh <chat_id> [url]
#
# Env:
#   ORION_MINIAPP_URL  Default URL if not passed as arg2.
#   TELEGRAM_BOT_TOKEN Optional. If unset, falls back to ~/.openclaw/secrets/telegram.token.
#   ORION_SUPPRESS_TELEGRAM If set truthy (1/true/yes/on), do not send (exit 0).
#   TELEGRAM_SUPPRESS       Alias for ORION_SUPPRESS_TELEGRAM.

CHAT_ID="${1:-}"
URL="${2:-${ORION_MINIAPP_URL:-}}"

if [[ -z "${CHAT_ID}" ]]; then
  echo "Usage: scripts/telegram_send_miniapp_button.sh <chat_id> [url]" >&2
  exit 2
fi

if [[ -z "${URL}" ]]; then
  echo "Missing Mini App URL. Provide arg2 or set ORION_MINIAPP_URL." >&2
  exit 2
fi

SUPPRESS_RAW="${ORION_SUPPRESS_TELEGRAM:-${TELEGRAM_SUPPRESS:-}}"
SUPPRESS="$(printf '%s' "${SUPPRESS_RAW}" | tr '[:upper:]' '[:lower:]')"
if [[ "${SUPPRESS}" == "1" || "${SUPPRESS}" == "true" || "${SUPPRESS}" == "yes" || "${SUPPRESS}" == "y" || "${SUPPRESS}" == "on" ]]; then
  echo "TELEGRAM_SUPPRESSED"
  exit 0
fi

TOKEN="${TELEGRAM_BOT_TOKEN:-}"
if [[ -z "${TOKEN}" ]]; then
  TOKEN="$(tr -d '\r\n' < "${HOME}/.openclaw/secrets/telegram.token" 2>/dev/null || true)"
fi
if [[ -z "${TOKEN}" ]]; then
  echo "Missing TELEGRAM_BOT_TOKEN and could not read ~/.openclaw/secrets/telegram.token" >&2
  exit 2
fi

REPLY_MARKUP="$(node -e 'const url=process.argv[1]; console.log(JSON.stringify({inline_keyboard:[[{text:"Open Dashboard", web_app:{url}}]]}));' "${URL}")"

curl -fsS "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -H "content-type: application/json" \
  -d "$(node -e 'const chat_id=process.argv[1]; const reply_markup=process.argv[2]; console.log(JSON.stringify({chat_id, text:"Open ORION Network Dashboard:", reply_markup: JSON.parse(reply_markup)}));' "${CHAT_ID}" "${REPLY_MARKUP}")" \
  >/dev/null
