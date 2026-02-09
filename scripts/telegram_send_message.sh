#!/usr/bin/env bash
set -euo pipefail

# Send a plain Telegram message using the ORION bot token.
#
# Usage:
#   scripts/telegram_send_message.sh <chat_id> <text...>
#
# Env:
#   TELEGRAM_BOT_TOKEN Optional. If unset, falls back to ~/.openclaw/secrets/telegram.token.

CHAT_ID="${1:-}"
shift || true
TEXT="${*:-}"

if [[ -z "${CHAT_ID}" ]] || [[ -z "${TEXT}" ]]; then
  echo "Usage: scripts/telegram_send_message.sh <chat_id> <text...>" >&2
  exit 2
fi

TOKEN="${TELEGRAM_BOT_TOKEN:-}"
if [[ -z "${TOKEN}" ]]; then
  TOKEN="$(tr -d '\r\n' < "${HOME}/.openclaw/secrets/telegram.token" 2>/dev/null || true)"
fi
if [[ -z "${TOKEN}" ]]; then
  echo "Missing TELEGRAM_BOT_TOKEN and could not read ~/.openclaw/secrets/telegram.token" >&2
  exit 2
fi

curl -fsS "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -H "content-type: application/json" \
  -d "$(node -e 'const chat_id=process.argv[1]; const text=process.argv[2]; console.log(JSON.stringify({chat_id, text, disable_web_page_preview:true}));' "${CHAT_ID}" "${TEXT}")" \
  >/dev/null
