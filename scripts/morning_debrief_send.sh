#!/usr/bin/env bash
set -euo pipefail

# Daily morning debrief email sender.
#
# This is designed to be run by OpenClaw cron (agent or system), or by a local
# scheduler (launchd/cron) without needing an LLM.
#
# Requirements:
# - curl, jq, node
# - AgentMail API key at ~/.openclaw/secrets/agentmail.api_key (see skills/agentmail/manifest.js)
#
# Env:
# - BRIEF_CITY (default: Pittsburgh)
# - BRIEF_MAX_ITEMS (default: 8)
# - BRIEF_TZ (default: America/New_York)
# - AGENTMAIL_FROM (default: orion_gatewaybot@agentmail.to)
# - AGENTMAIL_TO (default: boughs.gophers-2t@icloud.com)

have() { command -v "$1" >/dev/null 2>&1; }
for bin in curl jq node; do
  if ! have "$bin"; then
    echo "ERROR: missing dependency: $bin" >&2
    exit 1
  fi
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

CITY="${BRIEF_CITY:-Pittsburgh}"
MAX_ITEMS="${BRIEF_MAX_ITEMS:-8}"
TZNAME="${BRIEF_TZ:-America/New_York}"

FROM_INBOX="${AGENTMAIL_FROM:-orion_gatewaybot@agentmail.to}"
TO_EMAIL="${AGENTMAIL_TO:-boughs.gophers-2t@icloud.com}"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

inputs="$tmpdir/inputs.json"
body="$tmpdir/body.txt"

CITY="$CITY" MAX_ITEMS="$MAX_ITEMS" "$ROOT/scripts/brief_inputs.sh" >"$inputs"

local_date="$(TZ="$TZNAME" date '+%A, %B %d, %Y')"
subject="ORION Morning Brief — ${local_date}"

# Render a readable plain-text digest. Keep it scannable and link-friendly.
jq -r --arg date "$local_date" --arg city "$CITY" '
def hr($t): "\n" + $t + "\n" + ("-" * ($t|length)) + "\n";
def bullet($x): "- " + ($x|tostring);
def safe($x): if ($x==null) then "n/a" else ($x|tostring) end;
def short($x):
  if $x==null then null
  else ($x|tostring) as $t
  | ($t|gsub("\\s+";" ")|sub("^\\s+";"")|sub("\\s+$";"")) as $s
  | if ($s|length)==0 then null
    elif ($s|length) > 180 then ($s[0:177] + "...")
    else $s
    end
  end;
def itemLine($it):
  bullet(
    ($it.title|tostring)
    + (if ($it.source!=null and ($it.source|tostring|length)>0) then (" — " + ($it.source|tostring)) else "" end)
  )
  + "\n  " + ($it.link|tostring)
  + (if (short($it.snippet) != null) then ("\n  " + short($it.snippet)) else "" end);

"ORION Morning Brief — " + $date + "\n"
+ "City: " + $city + "\n"
+ "Generated: " + (.generatedAt|tostring) + " (UTC)\n"

+ hr("Weather")
+ ("Now: " + safe(.weather.current.desc) + " • " + safe(.weather.current.tempF) + "F (feels " + safe(.weather.current.feelsLikeF) + "F)"
    + " • Wind " + safe(.weather.current.windMph) + " mph " + safe(.weather.current.windDir)
    + " • Humidity " + safe(.weather.current.humidity) + "%\n")
+ ("Today: High " + safe(.weather.today.maxF) + "F / Low " + safe(.weather.today.minF) + "F"
    + " • Sunrise " + safe(.weather.today.sunrise) + " • Sunset " + safe(.weather.today.sunset) + "\n")

+ hr("AI / LLM News (Last ~24h)")
+ (if (.news.ai|length)==0 then "(no items)\n"
    else (.news.ai | map(itemLine(.)) | join("\n")) + "\n" end)

+ hr("Tech News (Last ~24h)")
+ (if (.news.tech|length)==0 then "(no items)\n"
    else (.news.tech | map(itemLine(.)) | join("\n")) + "\n" end)

+ hr("Pittsburgh News (Last ~24h)")
+ (if (.news.pittsburgh|length)==0 then "(no items)\n"
    else (.news.pittsburgh | map(itemLine(.)) | join("\n")) + "\n" end)

+ hr("Notes")
+ "If you want this to include a short ORION-written summary/commentary section, we can add an agent step later.\n"
' "$inputs" >"$body"

node "$ROOT/skills/agentmail/cli.js" send \
  --from "$FROM_INBOX" \
  --to "$TO_EMAIL" \
  --subject "$subject" \
  --text-file "$body" \
  >/dev/null

echo "sent: $TO_EMAIL"
