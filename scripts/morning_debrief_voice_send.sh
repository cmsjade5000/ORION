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
# - BRIEF_TTS_PRESET (optional override)   # (calm|narration|energetic|urgent)
#   - If unset, this script will not pass --preset and will defer to the
#     ElevenLabs skill default (OpenClaw env.vars ELEVENLABS_DEFAULT_PRESET).
# - BRIEF_MAX_SCRIPT_CHARS (default: 1400) # guardrail for TTS input
# - BRIEF_AT_ISO (optional)                # ISO-8601 UTC time to simulate brief start (e.g. 2026-02-11T12:00:00Z)
# - TELEGRAM_CHAT_ID (optional override; otherwise uses channels.telegram.allowFrom[0])
#
# Flags:
# - --send      Actually send to Telegram (default is dry-run)
# - --no-links  Do not send follow-up links message
# - --text-only Skip TTS/audio and send only the follow-up text (links + calendar)

have() { command -v "$1" >/dev/null 2>&1; }
for bin in curl jq node; do
  if ! have "$bin"; then
    echo "ERROR: missing dependency: $bin" >&2
    exit 1
  fi
done

SEND=0
SEND_LINKS=1
TEXT_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --send) SEND=1; shift ;;
    --no-links) SEND_LINKS=0; shift ;;
    --text-only) TEXT_ONLY=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--send] [--no-links] [--text-only]" >&2
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
PRESET="${BRIEF_TTS_PRESET:-}"
MAX_CHARS="${BRIEF_MAX_SCRIPT_CHARS:-1400}"
AT_ISO="${BRIEF_AT_ISO:-}"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

inputs="$tmpdir/inputs.json"
script_txt="$tmpdir/script.txt"
links_txt="$tmpdir/links.txt"
tts_stdout="$tmpdir/tts.stdout"
tts_stderr="$tmpdir/tts.stderr"

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
def cleanTitle($it):
  ($it.title|tostring) as $t
  | ($it.source // "" | tostring) as $s
  | if ($s|length)>0 and ($t|endswith(" - " + $s)) then $t[0:($t|length - (3 + ($s|length)))]
    elif ($s|length)>0 and ($t|endswith(" | " + $s)) then $t[0:($t|length - (3 + ($s|length)))]
    else $t end;
def oneLineTitle($it): clip(cleanTitle($it); 100);
def severeWeather:
  (
    [(.weather.current.desc // ""), (.weather.today.hourly[]?.desc // "")]
    | map(tostring)
    | join(" ")
  ) as $d
  | ($d | test("(tornado|hurricane|thunder|blizzard|freezing|ice|hail|warning|advisory|storm)"; "i"));
def severeWeatherBlock:
  if severeWeather then
    ("#urgent\n"
     + "Weather in " + $city + ": "
     + safe(.weather.current.desc) + ". "
     + safe(.weather.current.tempF) + " degrees now, feels like " + safe(.weather.current.feelsLikeF) + ". "
     + "High " + safe(.weather.today.maxF) + ", low " + safe(.weather.today.minF) + "."
     + "\n\n"
     + "#normal")
  else
    ("Weather in " + $city + ": "
     + safe(.weather.current.desc) + ". "
     + safe(.weather.current.tempF) + " degrees now, feels like " + safe(.weather.current.feelsLikeF) + ". "
     + "High " + safe(.weather.today.maxF) + ", low " + safe(.weather.today.minF) + ".")
  end;
def calLabel($c):
  if $c == "Appointment/Meeting" then "Appointment"
  elif $c == "Errands/Tasks" then "Task"
  elif $c == "Family" then "Family"
  elif $c == "Events" then "Event"
  elif $c == "Birthdays" then "Birthday"
  elif $c == "Work Shift Schedule" then "Work"
  elif $c == "Work" then "Work"
  else $c end;
def speakTitle($e):
  if ($e.calendar|tostring) == "Work Shift Schedule" then "Work"
  else ($e.title|tostring)
  end;
def eventLine($e):
  ($e.calendar|tostring) as $c
  | calLabel($c) as $label
  | speakTitle($e) as $t
  | if ($c == "Work Shift Schedule") then
      ("Work from " + ($e.startLocalTime|tostring) + " to " + ($e.endLocalTime|tostring))
    elif ($e.allDay == true) then
      (if $label == "Birthday" then ("All day: " + $t) else ("All day: " + $label + ". " + $t) end)
    elif ($e.status == "ongoing") then
      ("Right now: " + (if $label == "Work" then $t else ($label + ". " + $t) end) + ". Until " + ($e.endLocalTime|tostring))
    else
      ("At " + ($e.startLocalTime|tostring) + ": " + (if $label == "Work" then $t else ($label + ". " + $t) end))
    end;
def calendarSummary:
  if (.calendar.enabled != true) then "Calendar not configured."
  elif (.calendar.events|length)==0 then "No events scheduled."
  else
    (.calendar.events) as $ev
    | ($ev|length) as $n
    | ($ev[0:4] | map(eventLine(.)) | join(". ")) as $lines
    | if $n>4 then ($lines + ". And " + (($n-4)|tostring) + " more.") else ($lines + ".") end
  end;
def newsLine($arr; $label):
  if ($arr|length)==0 then ($label + ": no items.")
  else
    ($arr[0]) as $it
    | ($it.source // "") as $src
    | ($it.snippet // "") as $sn
    | (
        $label
        + " headline"
        + (if ($src|tostring|length)>0 then (" from " + ($src|tostring)) else "" end)
        + ": "
        + oneLineTitle($it)
        + "."
        + (
            if ($sn|tostring|length)>0
               and ((($sn|tostring|ascii_downcase) | contains(cleanTitle($it)|ascii_downcase)) | not)
               and (($sn|tostring|length) > 60)
            then (" Context: " + clip($sn; 140) + ".")
            else ""
            end
          )
      )
  end;

("#normal\n" + "Good morning, Cory. It is " + $date + ".")
 + "\n\n"
 + severeWeatherBlock
 + "\n\n"
 + ("Next 24 hours: " + calendarSummary)
 + "\n\n"
 + ("#narrative\n"
    + newsLine(.news.ai; "AI") + "\n\n"
    + newsLine(.news.tech; "Tech") + "\n\n"
    + newsLine(.news.pittsburgh; "Pittsburgh")
    + "\n\n"
    + "#normal")
 + "\n\n"
 + ("Links are coming in the next message.")
 | . as $s
 | if ($s|length) > $maxChars then ($s[0:$maxChars] + "…") else $s end
' "$inputs" >"$script_txt"

# Links message: scannable + clickable.
jq -r '
def html($s): ($s|tostring|@html);
def clip($s; $n):
  ($s|tostring|gsub("\\s+";" ")|sub("^\\s+";"")|sub("\\s+$";"")) as $t
  | if ($t|length) <= $n then $t else ($t[0:($n-1)] + "…") end;
def cleanTitle($it):
  ($it.title|tostring) as $t
  | ($it.source // "" | tostring) as $s
  | if ($s|length)>0 and ($t|endswith(" - " + $s)) then $t[0:($t|length - (3 + ($s|length)))]
    elif ($s|length)>0 and ($t|endswith(" | " + $s)) then $t[0:($t|length - (3 + ($s|length)))]
    else $t end;
def itemRow($it; $label):
  # Telegram HTML: clickable anchors; keep visible URLs minimal.
  # Render each item on a single line so truncation can be newline-safe.
  (
    "• "
    + "<a href=\"" + html($it.link) + "\">" + html(clip(cleanTitle($it); 140)) + "</a>"
    + (if ($it.source // null) then (" <i>(" + html($it.source) + ")</i>") else "" end)
  )
  + (
      # Only include a snippet if it adds information beyond repeating the title.
      ($it.snippet // "" | tostring) as $sn
      | if ($sn|length) > 60 and ((($sn|ascii_downcase) | contains((cleanTitle($it)|ascii_downcase))) | not)
        then ("\n  " + html(clip($sn; 160)))
        else ""
        end
    );
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

"<b>ORION Morning Brief links</b>\n"
 + (if (.calendar.enabled == true and (.calendar.events|length)>0) then "\n<b>Calendar (next 24h)</b>\n" + (.calendar.events[0:8] | map(eventRow(.)) | join("\n")) else "" end)
 + (if (.news.ai|length)>0 then "\n\n<b>AI</b>\n" + (.news.ai|map(itemRow(.;"AI"))|join("\n")) else "" end)
 + (if (.news.tech|length)>0 then "\n\n<b>Tech</b>\n" + (.news.tech|map(itemRow(.;"Tech"))|join("\n")) else "" end)
 + (if (.news.pittsburgh|length)>0 then "\n\n<b>Pittsburgh</b>\n" + (.news.pittsburgh|map(itemRow(.;"Pittsburgh"))|join("\n")) else "" end)
' "$inputs" >"$links_txt"

# Text-only mode: skip TTS entirely (useful when credits are low or voice is paused).
if [[ "$TEXT_ONLY" -eq 1 ]]; then
  if [[ "$SEND" -eq 0 ]]; then
    echo "DRY_RUN_OK"
    echo "TEXT_ONLY"
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

  SUPPRESS_RAW="${ORION_SUPPRESS_TELEGRAM:-${TELEGRAM_SUPPRESS:-}}"
  SUPPRESS="$(printf '%s' "${SUPPRESS_RAW}" | tr '[:upper:]' '[:lower:]')"
  if [[ "${SUPPRESS}" == "1" || "${SUPPRESS}" == "true" || "${SUPPRESS}" == "yes" || "${SUPPRESS}" == "y" || "${SUPPRESS}" == "on" ]]; then
    echo "TELEGRAM_SUPPRESSED"
    exit 0
  fi

  LINKS="$(
    node -e '
      const fs=require("fs");
      const p=process.argv[1];
      const lim=Number(process.argv[2]||"3800");
      const s=fs.readFileSync(p,"utf8");
      if(s.length<=lim){ process.stdout.write(s); process.exit(0); }
      const head=s.slice(0,lim);
      const i=head.lastIndexOf("\n");
      process.stdout.write((i>0?head.slice(0,i):head) + "\n…");
    ' "$links_txt" 3800
  )"
  curl -fsS "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -H "content-type: application/json" \
    -d "$(node -e 'const chat_id=process.argv[1]; const text=process.argv[2]; console.log(JSON.stringify({chat_id, text, parse_mode:"HTML", disable_web_page_preview:true}));' "$CHAT_ID" "$LINKS")" \
    >/dev/null

  echo "SENT_MORNING_TEXT_ONLY_OK"
  exit 0
fi

# Generate audio with the configured default voice, and the requested preset.
MEDIA_LINE=""
AUDIO_PATH=""
tts_args=(speak --text "$(cat "$script_txt")")
if [[ -n "${PRESET// /}" ]]; then
  tts_args+=(--preset "$PRESET")
fi

if node "$ROOT/skills/elevenlabs-tts/cli.js" "${tts_args[@]}" >"$tts_stdout" 2>"$tts_stderr"; then
  MEDIA_LINE="$(awk '/^MEDIA:/{print $0}' "$tts_stdout" | tail -n 1)"
else
  MEDIA_LINE=""
fi

if [[ -n "$MEDIA_LINE" ]]; then
  AUDIO_PATH="${MEDIA_LINE#MEDIA:}"
fi

if [[ "$SEND" -eq 0 ]]; then
  echo "DRY_RUN_OK"
  if [[ -n "$MEDIA_LINE" ]]; then
    echo "$MEDIA_LINE"
  else
    echo "WARN: TTS failed; no MEDIA line returned (see stderr in $tts_stderr)" >&2
  fi
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

SUPPRESS_RAW="${ORION_SUPPRESS_TELEGRAM:-${TELEGRAM_SUPPRESS:-}}"
SUPPRESS="$(printf '%s' "${SUPPRESS_RAW}" | tr '[:upper:]' '[:lower:]')"
if [[ "${SUPPRESS}" == "1" || "${SUPPRESS}" == "true" || "${SUPPRESS}" == "yes" || "${SUPPRESS}" == "y" || "${SUPPRESS}" == "on" ]]; then
  echo "TELEGRAM_SUPPRESSED"
  exit 0
fi

# If TTS failed (e.g., quota), fall back to sending the links/text message only.
if [[ -z "$MEDIA_LINE" || -z "$AUDIO_PATH" || ! -f "$AUDIO_PATH" ]]; then
  err_line="$(tail -n 1 "$tts_stderr" 2>/dev/null || true)"
  prefix="ORION Morning Brief — ${local_date}\n(Audio unavailable: TTS failed)\n"
  if [[ -n "${err_line// /}" ]]; then
    prefix="${prefix}Last error: ${err_line}\n\n"
  else
    prefix="${prefix}\n"
  fi
  LINKS="$(node -e '
    const fs=require("fs");
    const p=process.argv[1];
    const lim=Number(process.argv[2]||"3800");
    const s=fs.readFileSync(p,"utf8");
    const prefix=process.argv[3]||"";
    const full=prefix + s;
    if(full.length<=lim){ process.stdout.write(full); process.exit(0); }
    const head=full.slice(0,lim);
    const i=head.lastIndexOf(\"\\n\");
    process.stdout.write((i>0?head.slice(0,i):head) + \"\\n…\");
  ' "$links_txt" 3800 "$prefix")"
  curl -fsS "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -H "content-type: application/json" \
    -d "$(node -e 'const chat_id=process.argv[1]; const text=process.argv[2]; console.log(JSON.stringify({chat_id, text, parse_mode:"HTML", disable_web_page_preview:true}));' "$CHAT_ID" "$LINKS")" \
    >/dev/null
  echo "SENT_MORNING_TEXT_ONLY_OK"
  exit 0
fi

# Send audio first (caption is minimal; links come next as text).
curl -fsS "https://api.telegram.org/bot${TOKEN}/sendAudio" \
  -F "chat_id=${CHAT_ID}" \
  -F "audio=@${AUDIO_PATH}" \
  -F "caption=ORION Morning Brief (voice) — ${local_date} | preset: ${PRESET:-default}" \
  >/dev/null

if [[ "$SEND_LINKS" -eq 1 ]]; then
  # Keep under Telegram limits (best-effort) without cutting mid-line.
  LINKS="$(
    node -e '
      const fs=require("fs");
      const p=process.argv[1];
      const lim=Number(process.argv[2]||"3800");
      const s=fs.readFileSync(p,"utf8");
      if(s.length<=lim){ process.stdout.write(s); process.exit(0); }
      const head=s.slice(0,lim);
      const i=head.lastIndexOf("\n");
      process.stdout.write((i>0?head.slice(0,i):head) + "\n…");
    ' "$links_txt" 3800
  )"
  curl -fsS "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -H "content-type: application/json" \
    -d "$(node -e 'const chat_id=process.argv[1]; const text=process.argv[2]; console.log(JSON.stringify({chat_id, text, parse_mode:"HTML", disable_web_page_preview:true}));' "$CHAT_ID" "$LINKS")" \
    >/dev/null
fi

echo "SENT_MORNING_VOICE_OK"
