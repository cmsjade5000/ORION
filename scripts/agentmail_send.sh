#!/usr/bin/env bash
set -euo pipefail

# Send a plain-text email via AgentMail, and print a single status line.
#
# This is used to keep ORION honest: only report success if the AgentMail API
# returns a message_id.
#
# Usage:
#   ./scripts/agentmail_send.sh --to you@example.com --subject "Hi" --text "Body"
#   ./scripts/agentmail_send.sh --to you@example.com --subject "Hi" --text-file /tmp/body.txt
#   ./scripts/agentmail_send.sh you@example.com "Hi" "Body"  # positional compatibility
#
# Env:
# - AGENTMAIL_FROM (default: orion_gatewaybot@agentmail.to)

have() { command -v "$1" >/dev/null 2>&1; }
for bin in node jq; do
  if ! have "$bin"; then
    echo "EMAIL_SEND_FAILED: missing dependency: $bin" >&2
    exit 1
  fi
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FROM_INBOX="${AGENTMAIL_FROM:-orion_gatewaybot@agentmail.to}"

to=""
subject=""
text=""
text_file=""

# Positional compatibility:
#   agentmail_send.sh <to> <subject> <text...>
if [ "${#}" -gt 0 ] && [[ "${1}" != --* ]] && [[ "${1}" != -* ]]; then
  to="${1-}"
  subject="${2-}"
  shift 2 || true
  if [ "${#}" -gt 0 ]; then
    text="$*"
    shift "${#}" || true
  fi
fi

while [ "${#}" -gt 0 ]; do
  case "$1" in
    --to) to="${2-}"; shift 2 ;;
    --subject) subject="${2-}"; shift 2 ;;
    --text) text="${2-}"; shift 2 ;;
    --body) text="${2-}"; shift 2 ;; # common alias
    --text-file) text_file="${2-}"; shift 2 ;;
    -h|--help)
      sed -n '1,120p' "$0"
      exit 0
      ;;
    *)
      echo "EMAIL_SEND_FAILED: unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$to" ] || [ -z "$subject" ]; then
  echo "EMAIL_SEND_FAILED: missing --to or --subject" >&2
  exit 2
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

body_path="$tmpdir/body.txt"
if [ -n "$text_file" ]; then
  if [ ! -f "$text_file" ]; then
    echo "EMAIL_SEND_FAILED: missing file: $text_file" >&2
    exit 2
  fi
  cp "$text_file" "$body_path"
else
  if [ -z "$text" ]; then
    # Read stdin if --text/--text-file omitted.
    cat >"$body_path"
  else
    printf '%s\n' "$text" >"$body_path"
  fi
fi

out_json="$tmpdir/out.json"
if ! node "$ROOT/skills/agentmail/cli.js" send --from "$FROM_INBOX" --to "$to" --subject "$subject" --text-file "$body_path" >"$out_json" 2>"$tmpdir/err.log"; then
  err="$(sed -n '1,4p' "$tmpdir/err.log" | tr '\n' ' ' | sed 's/  */ /g')"
  echo "EMAIL_SEND_FAILED: ${err:-unknown error}" >&2
  exit 1
fi

mid="$(jq -r '.message_id // empty' "$out_json" 2>/dev/null || true)"
if [ -z "$mid" ]; then
  echo "EMAIL_SEND_FAILED: AgentMail returned no message_id" >&2
  exit 1
fi

echo "SENT_EMAIL_OK message_id=$mid"
