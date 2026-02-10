#!/usr/bin/env bash
set -euo pipefail

# Fetch structured inputs for the morning debrief email.
# Output JSON on stdout.
#
# Requirements:
# - curl
# - jq
# - node (for rss_extract.mjs)

CITY="${CITY:-Pittsburgh}"
MAX_ITEMS="${MAX_ITEMS:-8}"
AI_MAX_ITEMS="${AI_MAX_ITEMS:-}"
TECH_MAX_ITEMS="${TECH_MAX_ITEMS:-}"
PGH_MAX_ITEMS="${PGH_MAX_ITEMS:-}"

BRIEF_CALENDAR_NAMES="${BRIEF_CALENDAR_NAMES:-}"
BRIEF_CALENDAR_WINDOW_HOURS="${BRIEF_CALENDAR_WINDOW_HOURS:-24}"
BRIEF_CALENDAR_INCLUDE_ALLDAY="${BRIEF_CALENDAR_INCLUDE_ALLDAY:-1}"
BRIEF_TZ="${BRIEF_TZ:-}"
BRIEF_AT_ISO="${BRIEF_AT_ISO:-}"

# Default to a small total link count (2-5 total) unless explicitly overridden.
# If MAX_ITEMS is set, it acts as a fallback cap.
if [ -z "${AI_MAX_ITEMS}" ]; then AI_MAX_ITEMS="2"; fi
if [ -z "${TECH_MAX_ITEMS}" ]; then TECH_MAX_ITEMS="2"; fi
if [ -z "${PGH_MAX_ITEMS}" ]; then PGH_MAX_ITEMS="1"; fi

# Allow legacy MAX_ITEMS to override if it's smaller (global guard).
if [ "${MAX_ITEMS}" -lt "${AI_MAX_ITEMS}" ]; then AI_MAX_ITEMS="${MAX_ITEMS}"; fi
if [ "${MAX_ITEMS}" -lt "${TECH_MAX_ITEMS}" ]; then TECH_MAX_ITEMS="${MAX_ITEMS}"; fi
if [ "${MAX_ITEMS}" -lt "${PGH_MAX_ITEMS}" ]; then PGH_MAX_ITEMS="${MAX_ITEMS}"; fi

have() { command -v "$1" >/dev/null 2>&1; }
for bin in curl jq node; do
  if ! have "$bin"; then
    echo "ERROR: missing dependency: $bin" >&2
    exit 1
  fi
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RSS_EXTRACT="$ROOT/scripts/rss_extract.mjs"

if [ ! -f "$RSS_EXTRACT" ]; then
  echo "ERROR: missing: $RSS_EXTRACT" >&2
  exit 1
fi

# Optional: load calendar prefs from OpenClaw config env.vars (non-secret) so
# manual runs match the gateway service defaults.
if [[ -z "${BRIEF_CALENDAR_NAMES// /}" ]]; then
  CFG="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"
  if [[ -f "$CFG" ]]; then
    v="$(jq -r '.env.vars.BRIEF_CALENDAR_NAMES // empty' "$CFG" 2>/dev/null || true)"
    if [[ -n "${v// /}" && "$v" != "null" ]]; then BRIEF_CALENDAR_NAMES="$v"; fi
    v="$(jq -r '.env.vars.BRIEF_CALENDAR_WINDOW_HOURS // empty' "$CFG" 2>/dev/null || true)"
    if [[ -n "${v// /}" && "$v" != "null" ]]; then BRIEF_CALENDAR_WINDOW_HOURS="$v"; fi
    v="$(jq -r '.env.vars.BRIEF_CALENDAR_INCLUDE_ALLDAY // empty' "$CFG" 2>/dev/null || true)"
    if [[ -n "${v// /}" && "$v" != "null" ]]; then BRIEF_CALENDAR_INCLUDE_ALLDAY="$v"; fi
  fi
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

# Weather: wttr.in JSON (no key).
weather_json="$tmpdir/weather.json"
curl -fsSL "https://wttr.in/${CITY}?format=j1" -o "$weather_json"

target_date=""
if [[ -n "${BRIEF_AT_ISO}" && -n "${BRIEF_TZ}" ]]; then
  # Convert BRIEF_AT_ISO (UTC) to an epoch, then compute the local date string in BRIEF_TZ.
  epoch="$(TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%SZ" "${BRIEF_AT_ISO}" "+%s" 2>/dev/null || true)"
  if [[ -n "${epoch}" ]]; then
    target_date="$(TZ="${BRIEF_TZ}" date -r "${epoch}" "+%Y-%m-%d" 2>/dev/null || true)"
  fi
fi

weather="$(jq -c --arg targetDate "${target_date}" '{
  area: (.nearest_area[0].areaName[0].value // null),
  region: (.nearest_area[0].region[0].value // null),
  country: (.nearest_area[0].country[0].value // null),
  current: {
    tempF: (.current_condition[0].temp_F // null),
    feelsLikeF: (.current_condition[0].FeelsLikeF // null),
    desc: (.current_condition[0].weatherDesc[0].value // null),
    windMph: (.current_condition[0].windspeedMiles // null),
    windDir: (.current_condition[0].winddir16Point // null),
    humidity: (.current_condition[0].humidity // null),
    precipIn: (.current_condition[0].precipInches // null),
    uv: (.current_condition[0].uvIndex // null)
  },
  today: (
    if ($targetDate|length)>0 then
      (.weather | map(select(.date == $targetDate)) | .[0] // .weather[0])
    else
      .weather[0]
    end
  ) | {
    date: (.date // null),
    maxF: (.maxtempF // null),
    minF: (.mintempF // null),
    sunrise: (.astronomy[0].sunrise // null),
    sunset: (.astronomy[0].sunset // null),
    hourly: (
      .hourly
      | map({
        time: (.time // null),
        tempF: (.tempF // null),
        chanceRain: (.chanceofrain // null),
        chanceSnow: (.chanceofsnow // null),
        desc: (.weatherDesc[0].value // null)
      })
    )
  }
}' "$weather_json")"

rss_fetch() {
  local url="$1"
  local out="$2"
  curl -fsSL "$url" -o "$out"
}

# Google News RSS (no key). Use "when:1d" to bias to last ~24h.
ai_rss="$tmpdir/ai.rss.xml"
tech_rss="$tmpdir/tech.rss.xml"
pgh_rss="$tmpdir/pgh.rss.xml"

rss_fetch "https://news.google.com/rss/search?q=artificial%20intelligence%20OR%20LLM%20when%3A1d&hl=en-US&gl=US&ceid=US:en" "$ai_rss"
rss_fetch "https://news.google.com/rss/search?q=technology%20when%3A1d&hl=en-US&gl=US&ceid=US:en" "$tech_rss"
rss_fetch "https://news.google.com/rss/search?q=Pittsburgh%20when%3A1d&hl=en-US&gl=US&ceid=US:en" "$pgh_rss"

ai_items="$(node "$RSS_EXTRACT" --max "$AI_MAX_ITEMS" <"$ai_rss")"
tech_items="$(node "$RSS_EXTRACT" --max "$TECH_MAX_ITEMS" <"$tech_rss")"
pgh_items="$(node "$RSS_EXTRACT" --max "$PGH_MAX_ITEMS" <"$pgh_rss")"

now_iso="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

calendar_json="$(
  CAL_NAMES="$BRIEF_CALENDAR_NAMES" \
  CAL_WINDOW_HOURS="$BRIEF_CALENDAR_WINDOW_HOURS" \
  CAL_INCLUDE_ALLDAY="$BRIEF_CALENDAR_INCLUDE_ALLDAY" \
  CAL_START_ISO="$BRIEF_AT_ISO" \
  "$ROOT/scripts/calendar_events_fetch.sh" || echo '{"enabled":true,"error":"calendar_events_fetch failed","events":[]}'
)"

jq -n \
  --arg now "$now_iso" \
  --arg city "$CITY" \
  --argjson weather "$weather" \
  --argjson ai "$ai_items" \
  --argjson tech "$tech_items" \
  --argjson pgh "$pgh_items" \
  --argjson calendar "$calendar_json" \
  '{
    generatedAt: $now,
    city: $city,
    weather: $weather,
    calendar: $calendar,
    news: {
      ai: $ai,
      tech: $tech,
      pittsburgh: $pgh
    }
  }'
