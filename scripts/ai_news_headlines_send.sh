#!/usr/bin/env bash
set -euo pipefail

# Send a plain-text "AI News Headlines" email with real source links.
#
# This avoids hallucinated headlines by fetching Google News RSS via
# scripts/brief_inputs.sh and formatting items with an explicit Links section.
#
# Usage:
#   ./scripts/ai_news_headlines_send.sh --to you@example.com
#   ./scripts/ai_news_headlines_send.sh --to you@example.com --count 3 --subject "AI Headlines"
#
# Env:
# - CITY (default: Pittsburgh) used only for weather fetch inside brief_inputs.sh
# - AGENTMAIL_FROM (default: orion_gatewaybot@agentmail.to)

have() { command -v "$1" >/dev/null 2>&1; }
for bin in bash jq node curl; do
  if ! have "$bin"; then
    echo "EMAIL_SEND_FAILED: missing dependency: $bin" >&2
    exit 1
  fi
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

to=""
count="3"
subject=""

while [ "${#}" -gt 0 ]; do
  case "$1" in
    --to) to="${2-}"; shift 2 ;;
    --count) count="${2-}"; shift 2 ;;
    --subject) subject="${2-}"; shift 2 ;;
    -h|--help)
      sed -n '1,140p' "$0"
      exit 0
      ;;
    *)
      echo "EMAIL_SEND_FAILED: unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$to" ]; then
  echo "EMAIL_SEND_FAILED: missing --to" >&2
  exit 2
fi

if ! [[ "$count" =~ ^[0-9]+$ ]] || [ "$count" -lt 1 ] || [ "$count" -gt 8 ]; then
  echo "EMAIL_SEND_FAILED: --count must be 1..8" >&2
  exit 2
fi

if [ -z "$subject" ]; then
  # Local time subject is fine for a human-facing email.
  subject="Recent AI News Headlines — $(date '+%a %b %d, %Y')"
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

inputs="$tmpdir/inputs.json"
body="$tmpdir/body.txt"

# Fetch RSS-backed items; keep tech/pgh empty.
CITY="${CITY:-Pittsburgh}" \
AI_MAX_ITEMS="$count" \
TECH_MAX_ITEMS="0" \
PGH_MAX_ITEMS="0" \
bash "$ROOT/scripts/brief_inputs.sh" >"$inputs"

jq -r '
def hr($t): "\n" + $t + "\n" + ("-" * ($t|length)) + "\n";
def safe($x): (if $x == null then "" else ($x|tostring) end);
def itemLine($it; $idx):
  ($idx|tostring) + ". " + safe($it.title) +
  (if ($it.source|length) > 0 then " (" + $it.source + ")" else "" end);

"Hi Cory,\n\nHere are a few AI headlines from the last ~24 hours:\n"

+ (if (.news.ai|length)==0 then
     "\n(no items found; RSS fetch may have failed)\n"
   else
     "\n" + (.news.ai | to_entries | map(itemLine(.value; (.key+1))) | join("\n")) + "\n"
   end)

+ hr("Links")
+ (if (.news.ai|length)==0 then
     "(no links)\n"
   else
     (.news.ai | to_entries | map("AI-" + ((.key+1)|tostring) + ": " + (.value.link|tostring)) | join("\n")) + "\n"
   end)

+ "\nBest,\nORION\n"
' "$inputs" >"$body"

"$ROOT/scripts/agentmail_send.sh" --to "$to" --subject "$subject" --text-file "$body"

