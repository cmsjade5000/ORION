#!/usr/bin/env bash
set -euo pipefail

# Fetch upcoming calendar events from macOS Calendar.app using JXA (osascript -l JavaScript).
#
# Output: JSON to stdout.
#
# Env:
# - CAL_NAMES                Comma-separated calendar names to include (required to enable).
# - CAL_WINDOW_HOURS         Window size in hours from "now" (default: 24).
# - CAL_INCLUDE_ALLDAY       1 to include all-day events (default: 1).
# - CAL_START_ISO            Optional ISO-8601 start time (UTC recommended, e.g. 2026-02-11T12:00:00Z).
#
# Notes:
# - This is macOS-only (Calendar.app).
# - Calendar access may require granting automation permission to the calling process.

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo '{"enabled":false,"error":"calendar_events_fetch is macOS-only (Calendar.app).","events":[]}'  # no jq dependency
  exit 0
fi

CAL_NAMES="${CAL_NAMES:-}"
CAL_WINDOW_HOURS="${CAL_WINDOW_HOURS:-24}"
CAL_INCLUDE_ALLDAY="${CAL_INCLUDE_ALLDAY:-1}"

if [[ -z "${CAL_NAMES// /}" ]]; then
  echo '{"enabled":false,"events":[]}'
  exit 0
fi

export CAL_NAMES CAL_WINDOW_HOURS CAL_INCLUDE_ALLDAY

osascript -l JavaScript -e '
ObjC.import("stdlib");

function getenv(name, fallback) {
  const v = ObjC.unwrap($.getenv(name));
  if (v === undefined || v === null) return fallback;
  const s = String(v).trim();
  return s.length ? s : fallback;
}

function uniq(arr) {
  const out = [];
  const seen = new Set();
  for (const x of arr) {
    if (!seen.has(x)) {
      seen.add(x);
      out.push(x);
    }
  }
  return out;
}

function pad2(n) { return String(n).padStart(2, "0"); }
function fmtLocalTime(d) {
  // Local time (host timezone). Keep it simple for spoken + scannable output.
  const h24 = d.getHours();
  const m = pad2(d.getMinutes());
  const ampm = h24 >= 12 ? "PM" : "AM";
  const h12 = (h24 % 12) === 0 ? 12 : (h24 % 12);
  return `${h12}:${m} ${ampm}`;
}
function fmtLocalDate(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}`;
}

const names = uniq(
  getenv("CAL_NAMES", "")
    .split(",")
    .map(s => s.trim())
    .filter(Boolean)
);

const hoursRaw = getenv("CAL_WINDOW_HOURS", "24");
const windowHours = Number(hoursRaw);
const includeAllDay = getenv("CAL_INCLUDE_ALLDAY", "1") !== "0";

const startIso = getenv("CAL_START_ISO", "");
const now = startIso ? new Date(startIso) : new Date();
if (!(now instanceof Date) || isNaN(now.getTime())) {
  throw new Error("Invalid CAL_START_ISO: " + startIso);
}
const end = new Date(now.getTime() + (isFinite(windowHours) ? windowHours : 24) * 3600 * 1000);

const out = {
  enabled: true,
  generatedAt: new Date().toISOString(),
  startIso: now.toISOString(),
  endIso: end.toISOString(),
  windowHours: isFinite(windowHours) ? windowHours : 24,
  calendars: [],
  missingCalendars: [],
  events: [],
};

try {
  const cal = Application("Calendar");
  const calendars = cal.calendars();

  const selected = calendars.filter(c => names.includes(c.name()));
  out.calendars = selected.map(c => c.name());
  out.missingCalendars = names.filter(n => !out.calendars.includes(n));

  const events = [];
  for (const c of selected) {
    // Efficient overlap query: endDate > now && startDate < end.
    const es = c.events.whose({ endDate: { _greaterThan: now }, startDate: { _lessThan: end } })();
    for (const e of es) {
      const p = e.properties();
      const start = p.startDate;
      const finish = p.endDate;
      const allDay = !!p.alldayEvent;
      if (allDay && !includeAllDay) continue;
      events.push({
        calendar: c.name(),
        title: String(p.summary || "").trim() || "(untitled)",
        location: p.location ? String(p.location).trim() : null,
        allDay,
        status: (start <= now) ? "ongoing" : "upcoming",
        startIso: start.toISOString(),
        endIso: finish.toISOString(),
        startLocalDate: fmtLocalDate(start),
        startLocalTime: fmtLocalTime(start),
        endLocalTime: fmtLocalTime(finish),
      });
    }
  }

  events.sort((a, b) => a.startIso.localeCompare(b.startIso));
  out.events = events;
} catch (err) {
  out.error = String(err);
  out.events = [];
}

console.log(JSON.stringify(out));
' 2>&1 || echo '{"enabled":true,"error":"Calendar access failed (automation permission or scripting error).","events":[]}'
