#!/usr/bin/env bash
set -euo pipefail

# Daily morning debrief voice sender (Telegram).
#
# Produces:
# - a short spoken audio recap (MP3) via skills/elevenlabs-tts
# - an optional follow-up text message with links
#
# Designed to be run by OpenClaw cron or manually.
#
# Requirements:
# - curl, jq, node
# - ElevenLabs API key at ~/.openclaw/secrets/elevenlabs.api_key
# - Telegram bot token at ~/.openclaw/secrets/telegram.token
# - OpenClaw config at ~/.openclaw/openclaw.json (for chat_id allowFrom[0])
#
# Env:
# - BRIEF_CITY (default: Pittsburgh)
# - BRIEF_TZ (default: America/New_York)
# - BRIEF_AI_MAX_ITEMS (default: 2)
# - BRIEF_TECH_MAX_ITEMS (default: 2)
# - BRIEF_PGH_MAX_ITEMS (default: 1)
# - BRIEF_TTS_PRESET (default: narration)  # (calm|narration|energetic|urgent)
# - BRIEF_MAX_SCRIPT_CHARS (default: 1400) # guardrail for TTS input
# - BRIEF_AT_ISO (optional)                # ISO-8601 UTC time to simulate brief start (e.g. 2026-02-11T12:00:00Z)
# - TELEGRAM_CHAT_ID (optional override; otherwise uses channels.telegram.allowFrom[0])
#
# Flags:
# - --send      Actually send to Telegram (default is dry-run)
# - --no-links  Do not send follow-up links message

have() { command -v "$1" >/dev/null 2>&1; }
for bin in curl jq node; do
  if ! have "$bin"; then
    echo "ERROR: missing dependency: $bin" >&2
    exit 1
  fi
done

SEND=0
SEND_LINKS=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --send) SEND=1; shift ;;
    --no-links) SEND_LINKS=0; shift ;;
    -h|--help)
      echo "Usage: $0 [--send] [--no-links]" >&2
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"

CITY="${BRIEF_CITY:-Pittsburgh}"
TZNAME="${BRIEF_TZ:-America/New_York}"
AI_MAX_ITEMS="${BRIEF_AI_MAX_ITEMS:-2}"
TECH_MAX_ITEMS="${BRIEF_TECH_MAX_ITEMS:-2}"
PGH_MAX_ITEMS="${BRIEF_PGH_MAX_ITEMS:-1}"
PRESET="${BRIEF_TTS_PRESET:-narration}"
MAX_CHARS="${BRIEF_MAX_SCRIPT_CHARS:-1400}"
AT_ISO="${BRIEF_AT_ISO:-}"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

inputs="$tmpdir/inputs.json"
script_txt="$tmpdir/script.txt"
links_txt="$tmpdir/links.txt"

CITY="$CITY" BRIEF_TZ="$TZNAME" BRIEF_AT_ISO="$AT_ISO" \
  AI_MAX_ITEMS="$AI_MAX_ITEMS" TECH_MAX_ITEMS="$TECH_MAX_ITEMS" PGH_MAX_ITEMS="$PGH_MAX_ITEMS" \
  "$ROOT/scripts/brief_inputs.sh" >"$inputs"

if [[ -n "$AT_ISO" ]]; then
  epoch="$(TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%SZ" "$AT_ISO" "+%s" 2>/dev/null || true)"
  if [[ -n "$epoch" ]]; then
    local_date="$(TZ="$TZNAME" date -r "$epoch" '+%A, %B %d, %Y')"
  else
    local_date="$(TZ="$TZNAME" date '+%A, %B %d, %Y')"
  fi
else
  local_date="$(TZ="$TZNAME" date '+%A, %B %d, %Y')"
fi

# Spoken script: concise, structured, and link-free.
jq -r --arg date "$local_date" --arg city "$CITY" --arg preset "$PRESET" --argjson maxChars "$MAX_CHARS" '
def safe($x): if $x==null then "n/a" else ($x|tostring) end;
def norm($s): ($s|tostring|gsub("\\s+";" ")|sub("^\\s+";"")|sub("\\s+$";""));
def clip($s; $n):
  (norm($s)) as $t
  | if ($t|length) <= $n then $t else ($t[0:($n-1)] + "…") end;
def oneLineTitle($it): clip($it.title; 140);
def dispTitle($e):
  if ($e.calendar|tostring) == "Work Shift Schedule" then "Work"
  else ($e.title|tostring)
  end;
def eventLine($e):
  if ($e.allDay == true) then ("all day: " + dispTitle($e))
  elif ($e.status == "ongoing") then ("now: " + dispTitle($e) + ", until " + ($e.endLocalTime|tostring))
  elif ($e.calendar|tostring) == "Work Shift Schedule" then ("at " + ($e.startLocalTime|tostring) + ": " + dispTitle($e) + ", until " + ($e.endLocalTime|tostring))
  else ("at " + ($e.startLocalTime|tostring) + ": " + dispTitle($e))
  end;

("Good morning Cory. " + $date + ".")
 + "\n\n"
 + ("Weather in " + $city + ": "
    + safe(.weather.current.desc) + ". "
    + "Now " + safe(.weather.current.tempF) + " F, feels like " + safe(.weather.current.feelsLikeF) + ". "
    + "Wind " + safe(.weather.current.windMph) + " miles per hour. "
    + "Today, high " + safe(.weather.today.maxF) + " and low " + safe(.weather.today.minF) + ".")
 + "\n\n"
 + ("Calendar: "
    + (if (.calendar.enabled != true) then "not configured."
      elif (.calendar.events|length)==0 then "no events in the next 24 hours."
      else ((.calendar.events[0:4] | map(eventLine(.)) | join(". ")) + ".")
      end))
 + "\n\n"
 + ("AI news: "
    + (if (.news.ai|length)==0 then "no items." else ((.news.ai | map(oneLineTitle(.)) | join(". ")) + ".") end))
 + "\n\n"
 + ("Tech news: "
    + (if (.news.tech|length)==0 then "no items." else ((.news.tech | map(oneLineTitle(.)) | join(". ")) + ".") end))
 + "\n\n"
 + ("Pittsburgh news: "
    + (if (.news.pittsburgh|length)==0 then "no items." else ((.news.pittsburgh | map(oneLineTitle(.)) | join(". ")) + ".") end))
 + "\n\n"
 + ("I can send the links in a follow-up message.")
 | . as $s
 | if ($s|length) > $maxChars then ($s[0:$maxChars] + "…") else $s end
' "$inputs" >"$script_txt"

# Links message: scannable + clickable.
jq -r '
def domain($u):
  ($u|tostring
    | sub("^https?://";"")
    | split("/")[0]
  );
def itemLink($it; $label):
  "- " + $label + ": " + ($it.title|tostring) + "\n  " + domain($it.link) + "\n  " + ($it.link|tostring);
def dispTitle($e):
  if ($e.calendar|tostring) == "Work Shift Schedule" then "Work"
  else ($e.title|tostring)
  end;
def eventRow($e):
  if ($e.allDay == true) then ("- all day: " + dispTitle($e) + " (" + ($e.calendar|tostring) + ")")
  elif ($e.status == "ongoing") then ("- now: " + dispTitle($e) + " until " + ($e.endLocalTime|tostring) + " (" + ($e.calendar|tostring) + ")")
  elif ($e.calendar|tostring) == "Work Shift Schedule" then ("- " + ($e.startLocalTime|tostring) + "-" + ($e.endLocalTime|tostring) + ": " + dispTitle($e) + " (" + ($e.calendar|tostring) + ")")
  else ("- " + ($e.startLocalTime|tostring) + ": " + dispTitle($e) + " (" + ($e.calendar|tostring) + ")")
  end;

"ORION Morning Brief links\n"
 + (if (.calendar.enabled == true and (.calendar.events|length)>0) then "\nCalendar (next 24h)\n" + (.calendar.events[0:8] | map(eventRow(.)) | join("\n")) else "" end)
 + (if (.news.ai|length)>0 then "\nAI\n" + (.news.ai|to_entries|map(itemLink(.value; ("AI-" + ((.key+1)|tostring))))|join("\n")) else "" end)
 + (if (.news.tech|length)>0 then "\n\nTech\n" + (.news.tech|to_entries|map(itemLink(.value; ("TECH-" + ((.key+1)|tostring))))|join("\n")) else "" end)
 + (if (.news.pittsburgh|length)>0 then "\n\nPittsburgh\n" + (.news.pittsburgh|to_entries|map(itemLink(.value; ("PGH-" + ((.key+1)|tostring))))|join("\n")) else "" end)
' "$inputs" >"$links_txt"

# Generate audio with the configured default voice, and the requested preset.
MEDIA_LINE="$(
  node "$ROOT/skills/elevenlabs-tts/cli.js" speak \
    --preset "$PRESET" \
    --text "$(cat "$script_txt")" \
    | awk '/^MEDIA:/{print $0}' | tail -n 1
)"

if [[ -z "$MEDIA_LINE" ]]; then
  echo "ERROR: no MEDIA line returned from elevenlabs-tts" >&2
  exit 3
fi

AUDIO_PATH="${MEDIA_LINE#MEDIA:}"
if [[ ! -f "$AUDIO_PATH" ]]; then
  echo "ERROR: audio file missing: $AUDIO_PATH" >&2
  exit 4
fi

if [[ "$SEND" -eq 0 ]]; then
  echo "DRY_RUN_OK"
  echo "$MEDIA_LINE"
  exit 0
fi

if [[ ! -f "$CFG" ]]; then
  echo "ERROR: OpenClaw config not found: $CFG" >&2
  exit 2
fi

CHAT_ID="${TELEGRAM_CHAT_ID:-}"
if [[ -z "$CHAT_ID" ]]; then
  CHAT_ID="$(jq -r '.channels.telegram.allowFrom[0] // empty' "$CFG")"
fi
if [[ -z "$CHAT_ID" || "$CHAT_ID" == "null" ]]; then
  echo "ERROR: Could not determine Telegram chat id (channels.telegram.allowFrom[0])" >&2
  exit 2
fi

TOKEN="$(tr -d '\r\n' < "$HOME/.openclaw/secrets/telegram.token" 2>/dev/null || true)"
if [[ -z "$TOKEN" ]]; then
  echo "ERROR: Missing ~/.openclaw/secrets/telegram.token" >&2
  exit 2
fi

# Send audio first (caption is minimal; links come next as text).
curl -fsS "https://api.telegram.org/bot${TOKEN}/sendAudio" \
  -F "chat_id=${CHAT_ID}" \
  -F "audio=@${AUDIO_PATH}" \
  -F "caption=ORION Morning Brief (voice) — ${local_date} | preset: ${PRESET}" \
  >/dev/null

if [[ "$SEND_LINKS" -eq 1 ]]; then
  # Keep under Telegram limits (best-effort).
  LINKS="$(cat "$links_txt" | head -c 3500)"
  curl -fsS "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -H "content-type: application/json" \
    -d "$(node -e 'const chat_id=process.argv[1]; const text=process.argv[2]; console.log(JSON.stringify({chat_id, text, disable_web_page_preview:true}));' "$CHAT_ID" "$LINKS")" \
    >/dev/null
fi

echo "SENT_MORNING_VOICE_OK"
