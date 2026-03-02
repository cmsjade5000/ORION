#!/usr/bin/env bash
set -euo pipefail

# Send a Telegram message using the ORION bot token.
#
# Usage:
#   scripts/telegram_send_message.sh <chat_id> <text...>
#
# Env:
#   TELEGRAM_BOT_TOKEN Optional. If unset, falls back to ~/.openclaw/secrets/telegram.token.
#   ORION_SUPPRESS_TELEGRAM If set truthy (1/true/yes/on), do not send (exit 0).
#   TELEGRAM_SUPPRESS       Alias for ORION_SUPPRESS_TELEGRAM.
#   TELEGRAM_PARSE_MODE     Optional: HTML, Markdown, or MarkdownV2.
#   TELEGRAM_DISABLE_WEB_PREVIEW Optional. Defaults to true. Set falsey to enable previews.
#   TELEGRAM_MAX_CHARS      Optional positive int. Max chars per sendMessage chunk (default: 3800).
#   TELEGRAM_REPLY_TO_MESSAGE_ID Optional positive int for first sendMessage chunk only.
#   TELEGRAM_STREAM_DRAFT   If truthy, send incremental draft updates before final send.
#   TELEGRAM_STREAM_CHUNK_CHARS  Prefix growth per draft update (default: 280).
#   TELEGRAM_STREAM_STEP_MS      Delay between draft updates in ms (default: 220).
#   TELEGRAM_STREAM_DRAFT_ID     Optional positive integer draft id for deterministic animation.

CHAT_ID="${1:-}"
shift || true
TEXT="${*:-}"

if [[ -z "${CHAT_ID}" ]] || [[ -z "${TEXT}" ]]; then
  echo "Usage: scripts/telegram_send_message.sh <chat_id> <text...>" >&2
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

is_truthy() {
  local v="${1:-}"
  v="$(printf '%s' "${v}" | tr '[:upper:]' '[:lower:]')"
  [[ "${v}" == "1" || "${v}" == "true" || "${v}" == "yes" || "${v}" == "y" || "${v}" == "on" ]]
}

is_falsey() {
  local v="${1:-}"
  v="$(printf '%s' "${v}" | tr '[:upper:]' '[:lower:]')"
  [[ "${v}" == "0" || "${v}" == "false" || "${v}" == "no" || "${v}" == "n" || "${v}" == "off" ]]
}

PARSE_MODE=""
DISABLE_WEB_PREVIEW="true"
MAX_CHARS=3800
REPLY_TO_MESSAGE_ID=""
DRAFT_ID=""

resolve_parse_mode() {
  local raw="${TELEGRAM_PARSE_MODE:-}"
  if [[ -z "${raw}" ]]; then
    PARSE_MODE=""
    return
  fi
  case "${raw}" in
    HTML|Markdown|MarkdownV2)
      PARSE_MODE="${raw}"
      ;;
    *)
      echo "Invalid TELEGRAM_PARSE_MODE: ${raw} (expected HTML, Markdown, or MarkdownV2)" >&2
      exit 2
      ;;
  esac
}

resolve_web_preview() {
  local raw="${TELEGRAM_DISABLE_WEB_PREVIEW:-}"
  if [[ -z "${raw}" ]]; then
    DISABLE_WEB_PREVIEW="true"
    return
  fi
  if is_truthy "${raw}"; then
    DISABLE_WEB_PREVIEW="true"
    return
  fi
  if is_falsey "${raw}"; then
    DISABLE_WEB_PREVIEW="false"
    return
  fi
  echo "Invalid TELEGRAM_DISABLE_WEB_PREVIEW: ${raw}" >&2
  exit 2
}

resolve_max_chars() {
  local raw="${TELEGRAM_MAX_CHARS:-3800}"
  if [[ "${raw}" =~ ^[0-9]+$ ]] && (( raw > 0 )); then
    MAX_CHARS="${raw}"
    return
  fi
  echo "Invalid TELEGRAM_MAX_CHARS: ${raw} (expected positive integer)" >&2
  exit 2
}

resolve_reply_to_id() {
  local raw="${TELEGRAM_REPLY_TO_MESSAGE_ID:-}"
  if [[ -z "${raw}" ]]; then
    REPLY_TO_MESSAGE_ID=""
    return
  fi
  if [[ "${raw}" =~ ^[0-9]+$ ]] && (( raw > 0 )); then
    REPLY_TO_MESSAGE_ID="${raw}"
    return
  fi
  echo "Invalid TELEGRAM_REPLY_TO_MESSAGE_ID: ${raw} (expected positive integer)" >&2
  exit 2
}

resolve_parse_mode
resolve_web_preview
resolve_max_chars
resolve_reply_to_id

build_payload() {
  local kind="${1:-send}"
  local text="${2:-}"
  local include_reply="${3:-1}"
  if [[ "${kind}" == "send" ]]; then
    node -e '
const chat_id = process.argv[1];
const text = process.argv[2];
const disable_preview = process.argv[3] === "true";
const parse_mode = process.argv[4];
const reply_id = process.argv[5];
const include_reply = process.argv[6] === "1";
const payload = { chat_id, text, disable_web_page_preview: disable_preview };
if (parse_mode) payload.parse_mode = parse_mode;
if (include_reply && reply_id) payload.reply_to_message_id = Number(reply_id);
console.log(JSON.stringify(payload));
' "${CHAT_ID}" "${text}" "${DISABLE_WEB_PREVIEW}" "${PARSE_MODE}" "${REPLY_TO_MESSAGE_ID}" "${include_reply}"
    return
  fi
  if [[ "${kind}" == "draft" ]]; then
    node -e 'const chat_id=process.argv[1]; const draft_id=Number(process.argv[2]); const text=process.argv[3]; console.log(JSON.stringify({chat_id, draft_id, text}));' "${CHAT_ID}" "${DRAFT_ID}" "${text}"
    return
  fi
  node -e 'const chat_id=process.argv[1]; console.log(JSON.stringify({chat_id}));' "${CHAT_ID}"
}

telegram_api_call() {
  local method="${1:-}"
  local payload="${2:-}"
  local out=""
  out="$(curl -sS "https://api.telegram.org/bot${TOKEN}/${method}" -H "content-type: application/json" -d "${payload}" 2>&1)" || {
    echo "Telegram API ${method} request failed: ${out}" >&2
    return 1
  }
  local status=""
  status="$(printf '%s' "${out}" | node -e 'let s="";process.stdin.on("data",d=>s+=d);process.stdin.on("end",()=>{try{const j=JSON.parse(s);if(j&&j.ok){process.stdout.write("ok");return;}const code=(j&&j.error_code!=null)?String(j.error_code):"";const desc=(j&&j.description)?String(j.description):"unknown error";process.stdout.write(`err:${code}:${desc}`);}catch(e){process.stdout.write(`parse:${e.message}`);}});')"
  if [[ "${status}" == "ok" ]]; then
    return 0
  fi
  echo "Telegram API ${method} error (${status})" >&2
  return 1
}

emit_chunks() {
  local text="${1:-}"
  local limit="${2:-3800}"
  node -e '
const text = process.argv[1] ?? "";
const limit = Number(process.argv[2] ?? 3800);
if (!Number.isFinite(limit) || limit <= 0) process.exit(2);
let index = 0;
while (index < text.length) {
  let end = Math.min(index + limit, text.length);
  if (end < text.length) {
    const window = text.slice(index, end);
    const lastNewline = window.lastIndexOf("\n");
    const minNewlineIndex = Math.floor(limit * 0.5);
    if (lastNewline >= minNewlineIndex) {
      end = index + lastNewline + 1;
    }
  }
  process.stdout.write(text.slice(index, end));
  process.stdout.write("\0");
  index = end;
}
' "${text}" "${limit}"
}

send_final_message() {
  local include_reply="1"
  while IFS= read -r -d '' chunk; do
    telegram_api_call "sendMessage" "$(build_payload send "${chunk}" "${include_reply}")" || return 1
    include_reply="0"
  done < <(emit_chunks "${TEXT}" "${MAX_CHARS}")
  return 0
}

stream_via_drafts() {
  local chunk_raw="${TELEGRAM_STREAM_CHUNK_CHARS:-280}"
  local step_raw="${TELEGRAM_STREAM_STEP_MS:-220}"
  local chunk=280
  local step=220

  if [[ "${chunk_raw}" =~ ^[0-9]+$ ]] && (( chunk_raw > 0 )); then
    chunk="${chunk_raw}"
  fi
  if [[ "${step_raw}" =~ ^[0-9]+$ ]]; then
    step="${step_raw}"
  fi

  local total="${#TEXT}"
  if (( total <= chunk )); then
    return 2
  fi

  local ts_ms
  ts_ms="$(date +%s)"
  ts_ms="$((ts_ms * 1000))"
  local draft_raw="${TELEGRAM_STREAM_DRAFT_ID:-}"
  if [[ "${draft_raw}" =~ ^[0-9]+$ ]] && (( draft_raw > 0 )); then
    DRAFT_ID="${draft_raw}"
  else
    DRAFT_ID="$((((ts_ms + $$) % 2000000000) + 1))"
  fi

  local i="${chunk}"
  while (( i < total )); do
    local partial="${TEXT:0:i}"
    telegram_api_call "sendMessageDraft" "$(build_payload draft "${partial}")" || return 1
    if (( step > 0 )); then
      sleep "$(printf '%d.%03d' $((step / 1000)) $((step % 1000)))"
    fi
    i=$((i + chunk))
  done

  return 0
}

if is_truthy "${TELEGRAM_STREAM_DRAFT:-}"; then
  if stream_via_drafts; then
    :
  else
    rc=$?
    if (( rc != 2 )); then
      echo "Draft streaming unavailable; falling back to sendMessage." >&2
    fi
  fi
fi

send_final_message
