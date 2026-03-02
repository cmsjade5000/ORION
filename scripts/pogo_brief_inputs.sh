#!/usr/bin/env bash
set -euo pipefail

# Build structured inputs for the Pokemon GO morning voice brief.
# Output JSON to stdout.

have() { command -v "$1" >/dev/null 2>&1; }
for bin in curl jq node; do
  if ! have "$bin"; then
    echo "ERROR: missing dependency: $bin" >&2
    exit 1
  fi
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw/openclaw.json}"

POGO_TZ="${POGO_TZ:-America/New_York}"
POGO_NEWS_MAX_ITEMS="${POGO_NEWS_MAX_ITEMS:-8}"
POGO_EVENTS_MAX_ITEMS="${POGO_EVENTS_MAX_ITEMS:-16}"
POGO_STALE_NEWS_HOURS="${POGO_STALE_NEWS_HOURS:-120}"
POGO_AT_ISO="${POGO_AT_ISO:-}"
POGO_PROFILE_TAG="${POGO_PROFILE_TAG:-shiny_hunter}"
POGO_METRICS_LOG="${POGO_METRICS_LOG:-$ROOT/tmp/pogo_brief_metrics.jsonl}"

POGO_CALENDAR_NAMES="${POGO_CALENDAR_NAMES:-}"
POGO_WORK_CALENDAR_NAMES="${POGO_WORK_CALENDAR_NAMES:-}"
POGO_COMMUTE_KEYWORDS="${POGO_COMMUTE_KEYWORDS:-commute,drive,train,bus,subway,uber,lyft}"
POGO_CALENDAR_WINDOW_HOURS="${POGO_CALENDAR_WINDOW_HOURS:-24}"
POGO_CALENDAR_INCLUDE_ALLDAY="${POGO_CALENDAR_INCLUDE_ALLDAY:-1}"
POGO_HTTP_CONNECT_TIMEOUT_SECONDS="${POGO_HTTP_CONNECT_TIMEOUT_SECONDS:-5}"
POGO_HTTP_MAX_TIME_SECONDS="${POGO_HTTP_MAX_TIME_SECONDS:-15}"
POGO_CALENDAR_TIMEOUT_SECONDS="${POGO_CALENDAR_TIMEOUT_SECONDS:-8}"

fetch_html_with_timeout() {
  local url="$1"
  local out="$2"
  if curl -fsSL \
    --connect-timeout "$POGO_HTTP_CONNECT_TIMEOUT_SECONDS" \
    --max-time "$POGO_HTTP_MAX_TIME_SECONDS" \
    "$url" -o "$out"; then
    return 0
  fi
  # Keep pipeline alive on transient network failures/timeouts.
  printf '<html><head><meta charset="utf-8"></head><body></body></html>\n' > "$out"
  return 1
}

if [[ -z "${POGO_CALENDAR_NAMES// /}" && -f "$CFG" ]]; then
  v="$(jq -r '.env.vars.POGO_CALENDAR_NAMES // empty' "$CFG" 2>/dev/null || true)"
  if [[ -n "${v// /}" ]]; then POGO_CALENDAR_NAMES="$v"; fi
fi

if [[ -z "${POGO_CALENDAR_NAMES// /}" && -f "$CFG" ]]; then
  v="$(jq -r '.env.vars.BRIEF_CALENDAR_NAMES // empty' "$CFG" 2>/dev/null || true)"
  if [[ -n "${v// /}" ]]; then POGO_CALENDAR_NAMES="$v"; fi
fi

if [[ -z "${POGO_WORK_CALENDAR_NAMES// /}" ]]; then
  POGO_WORK_CALENDAR_NAMES="$POGO_CALENDAR_NAMES"
fi

if [[ -n "${POGO_AT_ISO// /}" ]]; then
  NOW_ISO="$POGO_AT_ISO"
else
  NOW_ISO="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

news_html="$tmpdir/news.html"
events_html="$tmpdir/events.html"
pogo_json="$tmpdir/pogo.json"
cal_json="$tmpdir/calendar.json"

news_fetch_ok=1
events_fetch_ok=1
if ! fetch_html_with_timeout 'https://pokemongo.com/en/news/' "$news_html"; then
  news_fetch_ok=0
fi
if ! fetch_html_with_timeout 'https://pokemongo.com/en/events/' "$events_html"; then
  events_fetch_ok=0
fi

if ! node "$ROOT/scripts/pogo_extract.mjs" \
  --news-html "$news_html" \
  --events-html "$events_html" \
  --max-news "$POGO_NEWS_MAX_ITEMS" \
  --max-events "$POGO_EVENTS_MAX_ITEMS" \
  --tz "$POGO_TZ" \
  --now "$NOW_ISO" \
  --stale-hours "$POGO_STALE_NEWS_HOURS" > "$pogo_json"; then
  jq -n \
    --arg now "$NOW_ISO" \
    --arg tz "$POGO_TZ" \
    --argjson newsOk "$news_fetch_ok" \
    --argjson eventsOk "$events_fetch_ok" '
    {
      generatedAt: $now,
      local: { tz: $tz, dayName: "", todayDate: "" },
      news: [],
      todayEvents: [],
      weekEvents: [],
      shinySignals: [],
      freshness: {
        stale: true,
        confidence: "low",
        newsAgeHours: null,
        note: (
          if ($newsOk == 1 and $eventsOk == 1) then
            "official feed parsing failed; using fallback payload"
          else
            "official feed fetch timed out/failed; using fallback payload"
          end
        )
      }
    }
  ' > "$pogo_json"
fi

CAL_NAMES="$POGO_CALENDAR_NAMES" \
CAL_WINDOW_HOURS="$POGO_CALENDAR_WINDOW_HOURS" \
CAL_INCLUDE_ALLDAY="$POGO_CALENDAR_INCLUDE_ALLDAY" \
CAL_START_ISO="$NOW_ISO" \
CAL_OSASCRIPT_TIMEOUT_SECONDS="$POGO_CALENDAR_TIMEOUT_SECONDS" \
  "$ROOT/scripts/calendar_events_fetch.sh" > "$cal_json"

COMMUTE_REGEX="$({
  printf '%s' "$POGO_COMMUTE_KEYWORDS" |
    tr ',' '\n' |
    sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' |
    sed '/^$/d' |
    sed -E 's/[][(){}.^$+*?|\\/]/\\&/g' |
    paste -sd'|' -
} || true)"
if [[ -z "${COMMUTE_REGEX// /}" ]]; then
  COMMUTE_REGEX="commute"
fi

jq -n \
  --arg nowIso "$NOW_ISO" \
  --arg profileTag "$POGO_PROFILE_TAG" \
  --arg workCal "$POGO_WORK_CALENDAR_NAMES" \
  --arg commuteRegex "$COMMUTE_REGEX" \
  --arg metricsLog "$POGO_METRICS_LOG" \
  --argjson pogo "$(cat "$pogo_json")" \
  --argjson calendar "$(cat "$cal_json")" '

def splitcsv($s):
  ($s | split(",") | map(gsub("^\\s+|\\s+$";"")) | map(select(length>0)));
def epoch($iso):
  if ($iso|type) != "string" then null
  else
    ($iso
      | sub("\\.[0-9]+Z$";"Z")
      | strptime("%Y-%m-%dT%H:%M:%SZ")
      | mktime)
  end;
def isWorkCal($work; $cal):
  if ($work|length) == 0 then true else (($work | index($cal)) != null) end;
def weeklyArc($day):
  if $day == "Monday" then "Weekly arc: Mission kickoff. Build shiny momentum before midweek."
  elif $day == "Tuesday" then "Weekly arc: Resource day. Stack balls, berries, and incubator value."
  elif $day == "Wednesday" then "Weekly arc: Midweek push. Prioritize time-limited shiny checks."
  elif $day == "Thursday" then "Weekly arc: Prep day. Set up items and route for the weekend."
  elif $day == "Friday" then "Weekly arc: Weekend staging. Clear storage and tag trade candidates."
  elif $day == "Saturday" then "Weekly arc: Field ops day. Raid and event windows take priority."
  elif $day == "Sunday" then "Weekly arc: Reset day. Inventory cleanup and next-week setup."
  else "Weekly arc: Stay flexible and keep shiny checks active." end;

($calendar.events // []) as $events
| splitcsv($workCal) as $workCals
| ($events | map(select((.title|test("R096";"i")) and isWorkCal($workCals; (.calendar|tostring))))) as $workShifts
| ($events | map(select(.title|test($commuteRegex;"i")))) as $commuteEvents
| ($workShifts | sort_by(.startIso) | .[0] // null) as $nextShift
| (
    if $nextShift == null then null
    else
      ($commuteEvents
        | map(select(
            (.startLocalDate == $nextShift.startLocalDate)
            and ((epoch(.endIso) // -1) <= (epoch($nextShift.startIso) // 0))
            and (((epoch($nextShift.startIso) // 0) - (epoch(.endIso) // 0)) <= (6*3600))
          ))
        | sort_by(.endIso)
        | last // null)
    end
  ) as $matchedCommute
| (
    if $nextShift == null then
      {status:"no_shift", note:"No R096 work shift detected in the current 24-hour window."}
    elif $matchedCommute == null then
      {status:"missing", note:"R096 shift detected, but no commute event was found before shift start."}
    else
      (((epoch($nextShift.startIso) // 0) - (epoch($matchedCommute.endIso) // 0)) / 60 | floor) as $gap
      | if $gap < 20 then
          {status:"tight", gapMinutes:$gap, note:("Commute window is tight: only " + ($gap|tostring) + " minutes before shift start.")}
        elif $gap > 180 then
          {status:"early", gapMinutes:$gap, note:("Commute is scheduled very early: " + ($gap|tostring) + " minutes before shift start.")}
        else
          {status:"ok", gapMinutes:$gap, note:("Commute timing looks solid with about " + ($gap|tostring) + " minutes of buffer.")}
        end
    end
  ) as $commuteCheck
| (
    if ($commuteCheck.status == "missing" or $commuteCheck.status == "tight") then
      {level:"high", reason:"Shift commute risk detected.", recommendedPreset:"urgent"}
    elif (($pogo.todayEvents // []) | length) > 0 then
      {level:"medium", reason:"Pokemon GO events are active today.", recommendedPreset:"energetic"}
    else
      {level:"low", reason:"No immediate windows; run a steady shiny sweep.", recommendedPreset:"narration"}
    end
  ) as $urgency
| {
    generatedAt: (now|todateiso8601),
    nowIso: $nowIso,
    profile: {
      trainerCodename: "Cmsjade5000",
      goals: ["always_hunt_shinies"],
      level: 67,
      tag: $profileTag
    },
    pokemon: $pogo,
    calendar: $calendar,
    commute: {
      workCalendarNames: $workCals,
      keywordsRegex: $commuteRegex,
      nextShift: $nextShift,
      matchedCommute: $matchedCommute,
      check: $commuteCheck
    },
    weeklyArc: {
      dayName: ($pogo.local.dayName // ""),
      line: weeklyArc($pogo.local.dayName // "")
    },
    urgency: $urgency,
    metrics: {
      scaffolded: true,
      logPath: $metricsLog,
      notes: "Basic JSONL event logging is enabled. Aggregated analytics are deferred."
    }
  }
'
