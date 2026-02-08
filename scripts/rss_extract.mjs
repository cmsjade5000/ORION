#!/usr/bin/env node
/**
 * Minimal RSS/Atom extractor (no deps).
 *
 * Usage:
 *   node scripts/rss_extract.mjs --max 8 < rss.xml
 *
 * Output:
 *   JSON array: [{title, link}, ...]
 */

function parseArgs(argv) {
  const args = { max: 8 };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--max") {
      args.max = Number(argv[++i] ?? "8");
    }
  }
  if (!Number.isFinite(args.max) || args.max <= 0) args.max = 8;
  return args;
}

function decodeEntities(s) {
  return s
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'");
}

function firstMatch(text, re) {
  const m = text.match(re);
  return m ? m[1] : "";
}

function extractItems(xml) {
  const items = [];

  // RSS 2.0: <item> ... </item>
  const rssRe = /<item\b[^>]*>([\s\S]*?)<\/item>/gi;
  let m;
  while ((m = rssRe.exec(xml))) {
    items.push(m[1]);
  }
  if (items.length > 0) return { kind: "rss", blocks: items };

  // Atom: <entry> ... </entry>
  const atomRe = /<entry\b[^>]*>([\s\S]*?)<\/entry>/gi;
  while ((m = atomRe.exec(xml))) {
    items.push(m[1]);
  }
  return { kind: "atom", blocks: items };
}

function extractTitle(block) {
  const raw =
    firstMatch(block, /<title\b[^>]*><!\[CDATA\[([\s\S]*?)\]\]><\/title>/i) ||
    firstMatch(block, /<title\b[^>]*>([\s\S]*?)<\/title>/i);
  return decodeEntities(raw.replace(/\s+/g, " ").trim());
}

function extractLink(kind, block) {
  if (kind === "atom") {
    const href =
      firstMatch(block, /<link\b[^>]*href="([^"]+)"[^>]*>/i) ||
      firstMatch(block, /<link\b[^>]*href='([^']+)'[^>]*>/i);
    return decodeEntities(href.trim());
  }
  const raw =
    firstMatch(block, /<link\b[^>]*><!\[CDATA\[([\s\S]*?)\]\]><\/link>/i) ||
    firstMatch(block, /<link\b[^>]*>([\s\S]*?)<\/link>/i);
  return decodeEntities(raw.replace(/\s+/g, " ").trim());
}

async function main() {
  const { max } = parseArgs(process.argv);

  const chunks = [];
  for await (const c of process.stdin) chunks.push(c);
  const xml = chunks.join("");

  const { kind, blocks } = extractItems(xml);
  const out = [];
  for (const block of blocks) {
    const title = extractTitle(block);
    const link = extractLink(kind, block);
    if (!title || !link) continue;
    // Drop obvious feed self-referential entries.
    if (/^https?:\/\/news\.google\.com\//.test(link) && title.toLowerCase() === "google news") continue;
    out.push({ title, link });
    if (out.length >= max) break;
  }
  // Important: this must be valid JSON on stdout (no stray characters).
  process.stdout.write(JSON.stringify(out, null, 2) + "\n");
}

main().catch((err) => {
  console.error(String(err?.stack || err));
  process.exit(2);
});
