#!/usr/bin/env bash
set -euo pipefail

# Pokemon GO 60-second morning voice brief sender (Telegram).
#
# Produces:
# - a shiny-first 60s voice briefing (MP3 via elevenlabs-tts)
# - optional follow-up text with links + quick commands

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
PROMPT_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --send) SEND=1; shift ;;
    --no-links) SEND_LINKS=0; shift ;;
    --text-only) TEXT_ONLY=1; shift ;;
    --prompt-only) PROMPT_ONLY=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--send] [--no-links] [--text-only] [--prompt-only]" >&2
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

MAX_CHARS="${POGO_SCRIPT_MAX_CHARS:-780}"
PRESET_OVERRIDE="${POGO_TTS_PRESET:-}"
METRICS_LOG="${POGO_METRICS_LOG:-$ROOT/tmp/pogo_brief_metrics.jsonl}"
LOCAL_TTS_FALLBACK="${POGO_LOCAL_TTS_FALLBACK:-1}"
LOCAL_TTS_VOICE="${POGO_LOCAL_TTS_VOICE:-Samantha}"
TZ_NAME="${POGO_TZ:-America/New_York}"

resolve_telegram_target() {
  if [[ ! -f "$CFG" ]]; then
    echo "ERROR: OpenClaw config not found: $CFG" >&2
    return 2
  fi

  CHAT_ID="${TELEGRAM_CHAT_ID:-}"
  if [[ -z "$CHAT_ID" ]]; then
    CHAT_ID="$(jq -r '.channels.telegram.allowFrom[0] // empty' "$CFG")"
  fi
  if [[ -z "$CHAT_ID" || "$CHAT_ID" == "null" ]]; then
    echo "ERROR: Could not determine Telegram chat id" >&2
    return 2
  fi

  TOKEN="$(tr -d '\r\n' < "$HOME/.openclaw/secrets/telegram.token" 2>/dev/null || true)"
  if [[ -z "$TOKEN" ]]; then
    echo "ERROR: Missing ~/.openclaw/secrets/telegram.token" >&2
    return 2
  fi

  SUPPRESS_RAW="${ORION_SUPPRESS_TELEGRAM:-${TELEGRAM_SUPPRESS:-}}"
  SUPPRESS="$(printf '%s' "${SUPPRESS_RAW}" | tr '[:upper:]' '[:lower:]')"
  if [[ "$SUPPRESS" == "1" || "$SUPPRESS" == "true" || "$SUPPRESS" == "yes" || "$SUPPRESS" == "y" || "$SUPPRESS" == "on" ]]; then
    echo "TELEGRAM_SUPPRESSED"
    return 10
  fi
  return 0
}

if [[ "$PROMPT_ONLY" -eq 1 ]]; then
  if [[ "$SEND" -eq 0 ]]; then
    echo "DRY_RUN_OK"
    echo "PROMPT_ONLY"
    exit 0
  fi

  if ! resolve_telegram_target; then
    rc="$?"
    if [[ "$rc" -eq 10 ]]; then
      exit 0
    fi
    exit "$rc"
  fi

  local_day="$(TZ="$TZ_NAME" date '+%A')"
  local_date="$(TZ="$TZ_NAME" date '+%Y-%m-%d')"
  PROMPT_MSG="$(cat <<EOF
<b>Pokemon GO Morning Ops — ${local_day}, ${local_date}</b>
How should I deliver today’s brief?
• /pogo_voice
• /pogo_text
EOF
)"

  curl -fsS "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -H "content-type: application/json" \
    -d "$(node -e 'const chat_id=process.argv[1]; const text=process.argv[2]; console.log(JSON.stringify({chat_id, text, parse_mode:"HTML", disable_web_page_preview:true}));' "$CHAT_ID" "$PROMPT_MSG")" \
    >/dev/null
  echo "SENT_POGO_DELIVERY_PROMPT_OK"
  exit 0
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

inputs="$tmpdir/inputs.json"
script_txt="$tmpdir/script.txt"
links_txt="$tmpdir/links.txt"
tts_stdout="$tmpdir/tts.stdout"
tts_stderr="$tmpdir/tts.stderr"

"$ROOT/scripts/pogo_brief_inputs.sh" > "$inputs"

local_day="$(jq -r '.pokemon.local.dayName // "today"' "$inputs")"
local_date="$(jq -r '.pokemon.local.todayDate // ""' "$inputs")"

jq -r --argjson maxChars "$MAX_CHARS" '
def clip($s; $n):
  ($s|tostring|gsub("\\s+";" ")|sub("^\\s+";"")|sub("\\s+$";"")) as $t
  | if ($t|length) <= $n then $t else ($t[0:($n-1)] + "…") end;
def firstOr($arr; $fallback):
  if ($arr|length)>0 then $arr[0] else $fallback end;
def fmtEvent($e):
  if $e == null then "No major event windows are confirmed today."
  else
    ($e.title|tostring)
    + " ("
    + ($e.startDate|tostring)
    + (if (($e.endDate // "")|length)>0 and ($e.endDate != $e.startDate) then (" to " + ($e.endDate|tostring)) else "" end)
    + ")"
  end;
def confidenceLine:
  "Intel confidence: " + (.pokemon.freshness.confidence|ascii_upcase)
  + (if .pokemon.freshness.stale then " due to stale official updates." else "." end);

("Good morning, Trainer Cory. " + (.weeklyArc.line|tostring))
+ "\n\n"
+ "Shiny radar: "
+ (
    if (.pokemon.shinySignals|length)>0 then
      (firstOr(.pokemon.shinySignals; {}) | .title // "Shiny opportunities detected")
    elif (.pokemon.todayEvents|length)>0 then
      (firstOr(.pokemon.todayEvents; {}) | .title // "Events active now")
    else
      "No explicit shiny callout in current official headlines; run a broad shiny-check route."
    end
  )
+ ".\n"
+ "Today in Pokemon GO: " + fmtEvent(firstOr(.pokemon.todayEvents; null)) + "\n"
+ "Shift and commute check: " + (.commute.check.note|tostring) + "\n"
+ confidenceLine + "\n"
+ "For text intel, use /pogo_today or /pogo_status."
| clip(.; $maxChars)
' "$inputs" > "$script_txt"

jq -r '
def clip($s; $n):
  ($s|tostring|gsub("\\s+";" ")|sub("^\\s+";"")|sub("\\s+$";"")) as $t
  | if ($t|length) <= $n then $t else ($t[0:($n-1)] + "…") end;
def item($e):
  "• <a href=\"" + ($e.link|@html) + "\">" + (clip($e.title; 120)|@html) + "</a>"
  + (if (($e.startDate // "")|length)>0 then (" <i>(" + (($e.startDate + (if (($e.endDate // "")|length)>0 and ($e.endDate != $e.startDate) then (" to " + $e.endDate) else "" end))|@html) + ")</i>") else "" end);

"<b>Pokemon GO Morning Ops</b>"
+ "\nShiny-first 60-second mode is active."
+ "\n\n<b>Active / Upcoming Events</b>\n"
+ (
    if (.pokemon.weekEvents|length)>0 then
      (.pokemon.weekEvents[0:6] | map(item(.)) | join("\n"))
    else
      "• No near-term official event cards parsed."
    end
  )
+ "\n\n<b>Latest News</b>\n"
+ (
    if (.pokemon.news|length)>0 then
      (.pokemon.news[0:5] | map("• <a href=\"" + (.link|@html) + "\">" + (clip(.title; 120)|@html) + "</a>") | join("\n"))
    else
      "• No official news cards parsed."
    end
  )
+ "\n\n<b>Quick Commands</b>\n"
+ "• /pogo_today\n• /pogo_status\n• /pogo_help"
+ "\n\n<b>Commute</b>\n"
+ ( .commute.check.note | @html )
' "$inputs" > "$links_txt"

# Resolve preset from urgency unless explicitly overridden.
PRESET="$(jq -r '.urgency.recommendedPreset // "narration"' "$inputs")"
if [[ -n "${PRESET_OVERRIDE// /}" ]]; then
  PRESET="$PRESET_OVERRIDE"
fi

# Text-only mode is useful when TTS credits are constrained.
if [[ "$TEXT_ONLY" -eq 1 ]]; then
  if [[ "$SEND" -eq 0 ]]; then
    echo "DRY_RUN_OK"
    echo "TEXT_ONLY"
    exit 0
  fi
fi

if [[ "$TEXT_ONLY" -eq 0 ]]; then
  MEDIA_LINE=""
  AUDIO_PATH=""
  TTS_PROVIDER=""
  TTS_ERROR=""
  if node "$ROOT/skills/elevenlabs-tts/cli.js" speak --text "$(cat "$script_txt")" --preset "$PRESET" >"$tts_stdout" 2>"$tts_stderr"; then
    MEDIA_LINE="$(awk '/^MEDIA:/{print $0}' "$tts_stdout" | tail -n 1)"
    if [[ -n "$MEDIA_LINE" ]]; then
      AUDIO_PATH="${MEDIA_LINE#MEDIA:}"
      TTS_PROVIDER="elevenlabs"
    fi
  else
    TTS_ERROR="$(tail -n 1 "$tts_stderr" 2>/dev/null || true)"
  fi

  # Local fallback when ElevenLabs is unavailable/quota-exceeded.
  if [[ -z "$AUDIO_PATH" || ! -f "$AUDIO_PATH" ]]; then
    fallback="$(printf '%s' "$LOCAL_TTS_FALLBACK" | tr '[:upper:]' '[:lower:]')"
    if [[ "$fallback" == "1" || "$fallback" == "true" || "$fallback" == "yes" || "$fallback" == "y" || "$fallback" == "on" ]]; then
      if command -v say >/dev/null 2>&1; then
        local_aiff="$tmpdir/pogo_local_tts.aiff"
        local_mp3="$tmpdir/pogo_local_tts.mp3"
        local_m4a="$tmpdir/pogo_local_tts.m4a"
        if say -v "$LOCAL_TTS_VOICE" -f "$script_txt" -o "$local_aiff" >/dev/null 2>&1; then
          if command -v ffmpeg >/dev/null 2>&1; then
            if ffmpeg -hide_banner -loglevel error -y -i "$local_aiff" -ac 1 -ar 44100 -b:a 128k "$local_mp3" >/dev/null 2>&1; then
              AUDIO_PATH="$local_mp3"
              MEDIA_LINE="MEDIA:$AUDIO_PATH"
              TTS_PROVIDER="local_say_ffmpeg"
            fi
          fi
          if [[ -z "$AUDIO_PATH" || ! -f "$AUDIO_PATH" ]]; then
            if command -v afconvert >/dev/null 2>&1; then
              if afconvert -f m4af -d aac "$local_aiff" "$local_m4a" >/dev/null 2>&1; then
                AUDIO_PATH="$local_m4a"
                MEDIA_LINE="MEDIA:$AUDIO_PATH"
                TTS_PROVIDER="local_say_afconvert"
              fi
            fi
          fi
        fi
      fi
    fi
  fi
else
  MEDIA_LINE=""
  AUDIO_PATH=""
  TTS_PROVIDER="text_only"
  TTS_ERROR=""
fi

if [[ "$SEND" -eq 0 ]]; then
  echo "DRY_RUN_OK"
  if [[ -n "$MEDIA_LINE" ]]; then
    echo "$MEDIA_LINE"
  fi
  exit 0
fi

if ! resolve_telegram_target; then
  rc="$?"
  if [[ "$rc" -eq 10 ]]; then
    exit 0
  fi
  exit "$rc"
fi

sent_mode="text_only"
tts_ok=0
if [[ "$TEXT_ONLY" -eq 0 && -n "$AUDIO_PATH" && -f "$AUDIO_PATH" ]]; then
  curl -fsS "https://api.telegram.org/bot${TOKEN}/sendAudio" \
    -F "chat_id=${CHAT_ID}" \
    -F "audio=@${AUDIO_PATH}" \
    -F "caption=Pokemon GO Morning Ops (voice) — ${local_day}, ${local_date} | preset: ${PRESET} | tts: ${TTS_PROVIDER:-unknown}" \
    >/dev/null
  sent_mode="voice"
  tts_ok=1
fi

if [[ "$SEND_LINKS" -eq 1 || "$sent_mode" == "text_only" ]]; then
  LINKS="$({
    node -e '
      const fs=require("fs");
      const p=process.argv[1];
      const lim=Number(process.argv[2]||"3800");
      const s=fs.readFileSync(p,"utf8");
      if(s.length<=lim){ process.stdout.write(s); process.exit(0); }
      const head=s.slice(0,lim);
      const i=head.lastIndexOf("\\n");
      process.stdout.write((i>0?head.slice(0,i):head) + "\\n…");
    ' "$links_txt" 3800
  } || true)"
  curl -fsS "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -H "content-type: application/json" \
    -d "$(node -e 'const chat_id=process.argv[1]; const text=process.argv[2]; console.log(JSON.stringify({chat_id, text, parse_mode:"HTML", disable_web_page_preview:true}));' "$CHAT_ID" "$LINKS")" \
    >/dev/null
fi

mkdir -p "$(dirname "$METRICS_LOG")"
{
  jq -n \
    --arg at "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
    --arg mode "$sent_mode" \
    --arg preset "$PRESET" \
    --arg day "$local_day" \
    --arg date "$local_date" \
    --arg provider "${TTS_PROVIDER:-unknown}" \
    --arg ttsErr "${TTS_ERROR:-}" \
    --argjson ttsOk "$tts_ok" \
    --argjson inputs "$(cat "$inputs")" '
    {
      at: $at,
      mode: $mode,
      preset: $preset,
      day: $day,
      date: $date,
      ttsProvider: $provider,
      ttsError: (if ($ttsErr|length)>0 then $ttsErr else null end),
      ttsOk: $ttsOk,
      confidence: ($inputs.pokemon.freshness.confidence // "unknown"),
      stale: ($inputs.pokemon.freshness.stale // null),
      urgency: ($inputs.urgency.level // "unknown"),
      commuteStatus: ($inputs.commute.check.status // "unknown")
    }
  '
} >> "$METRICS_LOG" || true

if [[ "$sent_mode" == "voice" ]]; then
  echo "SENT_POGO_MORNING_VOICE_OK"
else
  echo "SENT_POGO_MORNING_TEXT_ONLY_OK"
fi
