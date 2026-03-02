#!/usr/bin/env node
/**
 * Extract Pokemon GO news + events from official site HTML.
 *
 * Usage:
 *   node scripts/pogo_extract.mjs --news-html /tmp/news.html --events-html /tmp/events.html
 */

import fs from "node:fs";

function parseArgs(argv) {
  const args = {
    newsHtml: "",
    eventsHtml: "",
    maxNews: 8,
    maxEvents: 20,
    tz: "America/New_York",
    nowIso: new Date().toISOString(),
    staleHours: 120,
  };

  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--news-html") args.newsHtml = argv[++i] ?? "";
    else if (a === "--events-html") args.eventsHtml = argv[++i] ?? "";
    else if (a === "--max-news") args.maxNews = Number(argv[++i] ?? "8");
    else if (a === "--max-events") args.maxEvents = Number(argv[++i] ?? "20");
    else if (a === "--tz") args.tz = argv[++i] ?? "America/New_York";
    else if (a === "--now") args.nowIso = argv[++i] ?? args.nowIso;
    else if (a === "--stale-hours") args.staleHours = Number(argv[++i] ?? "120");
  }

  if (!Number.isFinite(args.maxNews) || args.maxNews < 1) args.maxNews = 8;
  if (!Number.isFinite(args.maxEvents) || args.maxEvents < 1) args.maxEvents = 20;
  if (!Number.isFinite(args.staleHours) || args.staleHours < 1) args.staleHours = 120;

  return args;
}

function decodeEntities(s) {
  return String(s)
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&nbsp;/g, " ");
}

function stripHtml(s) {
  return decodeEntities(String(s).replace(/<[^>]+>/g, " "))
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeLink(link) {
  const raw = String(link || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("/")) return `https://pokemongo.com${raw}`;
  return `https://pokemongo.com/${raw.replace(/^\/+/, "")}`;
}

function firstMatch(text, re) {
  const m = String(text).match(re);
  return m ? m[1] : "";
}

function ymdInTz(date, tz) {
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = fmt.formatToParts(date);
  const year = parts.find((p) => p.type === "year")?.value ?? "1970";
  const month = parts.find((p) => p.type === "month")?.value ?? "01";
  const day = parts.find((p) => p.type === "day")?.value ?? "01";
  return `${year}-${month}-${day}`;
}

function weekdayInTz(date, tz) {
  return new Intl.DateTimeFormat("en-US", { timeZone: tz, weekday: "long" }).format(date);
}

function addDaysYmd(ymd, days) {
  const m = String(ymd).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return ymd;
  const dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + days));
  return dt.toISOString().slice(0, 10);
}

function eventStatus(todayYmd, startDate, endDate) {
  if (!startDate) return "unknown";
  const end = endDate || startDate;
  if (end < todayYmd) return "past";
  if (startDate > todayYmd) return "upcoming";
  return "active";
}

function extractNewsCards(html, maxNews) {
  const out = [];
  const re = /<a\s+href="([^"]+)"[^>]*class="[^"]*_newsCard_[^"]*"[^>]*>([\s\S]*?)<\/a>/gi;
  let m;

  while ((m = re.exec(html)) && out.length < maxNews) {
    const link = normalizeLink(m[1]);
    const block = m[2];
    const title = stripHtml(
      firstMatch(block, /<div\s+class="_size:heading[^>]*>([\s\S]*?)<\/div>/i)
    );
    const tsRaw = firstMatch(block, /timestamp="(\d{10,13})"/i);
    const ts = Number(tsRaw);
    const publishedAt = Number.isFinite(ts) ? new Date(ts).toISOString() : null;
    if (!title || !link) continue;
    out.push({ title, link, publishedAt });
  }

  return out;
}

function extractEventCards(html, maxEvents) {
  const out = [];
  const re = /<a\s+href="([^"]+)"[^>]*class="[^"]*_eventsCard_[^"]*"[^>]*>([\s\S]*?)<\/a>/gi;
  let m;

  while ((m = re.exec(html)) && out.length < maxEvents) {
    const link = normalizeLink(m[1]);
    const block = m[2];
    const title = stripHtml(
      firstMatch(block, /<div\s+class="_size:heading[^>]*>([\s\S]*?)<\/div>/i)
    );
    const startDate = firstMatch(block, /startDate="(\d{4}-\d{2}-\d{2})"/i) || null;
    let endDate = firstMatch(block, /endDate="(\d{4}-\d{2}-\d{2})"/i) || null;
    if (!endDate && /\bendDate\b/i.test(block)) endDate = startDate;
    if (!title || !link || !startDate) continue;
    out.push({ title, link, startDate, endDate: endDate || startDate });
  }

  const dedup = [];
  const seen = new Set();
  for (const e of out) {
    const k = `${e.title}||${e.startDate}||${e.endDate}`;
    if (seen.has(k)) continue;
    seen.add(k);
    dedup.push(e);
  }
  return dedup;
}

function computeShinySignals(todayEvents, weekEvents, news) {
  const shinyRe = /(shiny|community\s*day|spotlight|raid\s*day|hatch\s*day|research\s*day|debut|go\s*fest|go\s*tour|legendary)/i;
  const out = [];

  for (const e of [...todayEvents, ...weekEvents]) {
    if (!shinyRe.test(e.title)) continue;
    out.push({
      source: "event",
      title: e.title,
      link: e.link,
      date: `${e.startDate}${e.endDate && e.endDate !== e.startDate ? ` to ${e.endDate}` : ""}`,
    });
    if (out.length >= 4) return out;
  }

  for (const n of news) {
    if (!shinyRe.test(n.title)) continue;
    out.push({ source: "news", title: n.title, link: n.link, date: n.publishedAt });
    if (out.length >= 4) return out;
  }

  return out;
}

function computeFreshness(now, news, staleHours) {
  const newest = news
    .map((n) => n.publishedAt)
    .filter(Boolean)
    .map((iso) => Date.parse(iso))
    .filter((n) => Number.isFinite(n))
    .sort((a, b) => b - a)[0];

  if (!Number.isFinite(newest)) {
    return {
      latestNewsAt: null,
      newsAgeHours: null,
      stale: true,
      confidence: "low",
      reasons: ["No timestamped Pokemon GO news items found."],
    };
  }

  const ageHours = (now.getTime() - newest) / 3600000;
  const stale = ageHours > staleHours;
  let confidence = "high";
  if (stale) confidence = "low";
  else if (ageHours > staleHours * 0.5) confidence = "medium";

  const reasons = [];
  if (stale) reasons.push(`Newest Pokemon GO news is older than ${staleHours}h.`);
  else reasons.push(`Newest Pokemon GO news age is ${Math.round(ageHours)}h.`);

  return {
    latestNewsAt: new Date(newest).toISOString(),
    newsAgeHours: Number(ageHours.toFixed(2)),
    stale,
    confidence,
    reasons,
  };
}

function computeUrgency(todayEvents, commuteStatus) {
  if (commuteStatus === "missing" || commuteStatus === "tight") {
    return {
      level: "high",
      reason: "Work shift commute risk detected.",
      recommendedPreset: "urgent",
    };
  }
  if (todayEvents.length > 0) {
    return {
      level: "medium",
      reason: "There are active Pokemon GO events today.",
      recommendedPreset: "energetic",
    };
  }
  return {
    level: "low",
    reason: "No high-pressure event windows detected.",
    recommendedPreset: "narration",
  };
}

function main() {
  const args = parseArgs(process.argv);
  if (!args.newsHtml || !args.eventsHtml) {
    throw new Error("--news-html and --events-html are required");
  }

  const now = new Date(args.nowIso);
  if (Number.isNaN(now.getTime())) {
    throw new Error(`Invalid --now value: ${args.nowIso}`);
  }

  const newsHtml = fs.readFileSync(args.newsHtml, "utf8");
  const eventsHtml = fs.readFileSync(args.eventsHtml, "utf8");

  const news = extractNewsCards(newsHtml, args.maxNews);
  const rawEvents = extractEventCards(eventsHtml, args.maxEvents);

  const todayYmd = ymdInTz(now, args.tz);
  const weekEndYmd = addDaysYmd(todayYmd, 6);
  const dayName = weekdayInTz(now, args.tz);

  const events = rawEvents.map((e) => ({
    ...e,
    status: eventStatus(todayYmd, e.startDate, e.endDate),
  }));

  const todayEvents = events.filter((e) => e.status === "active");
  const weekEvents = events.filter(
    (e) => (e.status === "active" || e.status === "upcoming") && e.startDate <= weekEndYmd
  );

  const shinySignals = computeShinySignals(todayEvents, weekEvents, news);
  const freshness = computeFreshness(now, news, args.staleHours);

  const out = {
    generatedAt: new Date().toISOString(),
    nowIso: now.toISOString(),
    tz: args.tz,
    local: {
      dayName,
      todayDate: todayYmd,
      weekEndDate: weekEndYmd,
    },
    freshness,
    news,
    events,
    todayEvents,
    weekEvents,
    shinySignals,
    urgencyBase: computeUrgency(todayEvents, "none"),
  };

  process.stdout.write(JSON.stringify(out, null, 2) + "\n");
}

main();
