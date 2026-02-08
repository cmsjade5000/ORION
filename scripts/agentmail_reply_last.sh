#!/usr/bin/env bash
set -euo pipefail

# Reply to the most recent received message (optionally from a specific sender)
# via AgentMail, and print a single status line with the sent message_id.
#
# Usage:
#   ./scripts/agentmail_reply_last.sh --from-email you@example.com --text "confirmed"
#   ./scripts/agentmail_reply_last.sh --from-email you@example.com --text-file /tmp/body.txt
#
# Env:
# - AGENTMAIL_FROM (default: orion_gatewaybot@agentmail.to)

have() { command -v "$1" >/dev/null 2>&1; }
for bin in node jq; do
  if ! have "$bin"; then
    echo "EMAIL_REPLY_FAILED: missing dependency: $bin" >&2
    exit 1
  fi
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FROM_INBOX="${AGENTMAIL_FROM:-orion_gatewaybot@agentmail.to}"

from_email=""
text=""
text_file=""

while [ "${#}" -gt 0 ]; do
  case "$1" in
    --from-email) from_email="${2-}"; shift 2 ;;
    --text) text="${2-}"; shift 2 ;;
    --body) text="${2-}"; shift 2 ;; # alias
    --text-file) text_file="${2-}"; shift 2 ;;
    -h|--help)
      sed -n '1,140p' "$0"
      exit 0
      ;;
    *)
      echo "EMAIL_REPLY_FAILED: unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

body_path="$tmpdir/body.txt"
if [ -n "$text_file" ]; then
  if [ ! -f "$text_file" ]; then
    echo "EMAIL_REPLY_FAILED: missing file: $text_file" >&2
    exit 2
  fi
  cp "$text_file" "$body_path"
else
  if [ -z "$text" ]; then
    cat >"$body_path"
  else
    printf '%s\n' "$text" >"$body_path"
  fi
fi

out_json="$tmpdir/out.json"
cmd=(node "$ROOT/skills/agentmail/cli.js" reply-last --from "$FROM_INBOX" --text-file "$body_path")
if [ -n "$from_email" ]; then
  cmd+=("--from-email" "$from_email")
fi

if ! "${cmd[@]}" >"$out_json" 2>"$tmpdir/err.log"; then
  err="$(sed -n '1,4p' "$tmpdir/err.log" | tr '\n' ' ' | sed 's/  */ /g')"
  echo "EMAIL_REPLY_FAILED: ${err:-unknown error}" >&2
  exit 1
fi

mid="$(jq -r '.sent.message_id // empty' "$out_json" 2>/dev/null || true)"
rid="$(jq -r '.repliedTo.message_id // empty' "$out_json" 2>/dev/null || true)"
if [ -z "$mid" ]; then
  echo "EMAIL_REPLY_FAILED: AgentMail returned no message_id" >&2
  exit 1
fi

if [ -n "$rid" ]; then
  echo "REPLY_EMAIL_OK message_id=$mid replied_to=$rid"
else
  echo "REPLY_EMAIL_OK message_id=$mid"
fi

