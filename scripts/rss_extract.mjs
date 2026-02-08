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
    .replace(/&apos;/g, "'")
    .replace(/&nbsp;/g, " ");
}

function firstMatch(text, re) {
  const m = text.match(re);
  return m ? m[1] : "";
}

function stripHtml(s) {
  // Good enough for RSS snippets (Google News uses <a> + <font>).
  return String(s)
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
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

function extractPubDate(kind, block) {
  if (kind === "atom") {
    const updated = firstMatch(block, /<updated\b[^>]*>([\s\S]*?)<\/updated>/i);
    const published = firstMatch(block, /<published\b[^>]*>([\s\S]*?)<\/published>/i);
    const raw = updated || published || "";
    return decodeEntities(String(raw).replace(/\s+/g, " ").trim());
  }
  const raw = firstMatch(block, /<pubDate\b[^>]*>([\s\S]*?)<\/pubDate>/i);
  return decodeEntities(String(raw || "").replace(/\s+/g, " ").trim());
}

function extractSource(kind, block) {
  if (kind === "atom") return "";
  const raw = firstMatch(block, /<source\b[^>]*>([\s\S]*?)<\/source>/i);
  return decodeEntities(String(raw || "").replace(/\s+/g, " ").trim());
}

function extractSnippet(kind, block) {
  const raw =
    firstMatch(block, /<description\b[^>]*><!\[CDATA\[([\s\S]*?)\]\]><\/description>/i) ||
    firstMatch(block, /<description\b[^>]*>([\s\S]*?)<\/description>/i) ||
    firstMatch(block, /<summary\b[^>]*>([\s\S]*?)<\/summary>/i);
  const cleaned = stripHtml(decodeEntities(String(raw || "")));
  return cleaned;
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
    const publishedAt = extractPubDate(kind, block);
    const source = extractSource(kind, block);
    const snippet = extractSnippet(kind, block);
    if (!title || !link) continue;
    // Drop obvious feed self-referential entries.
    if (/^https?:\/\/news\.google\.com\//.test(link) && title.toLowerCase() === "google news") continue;
    out.push({
      title,
      link,
      source: source || null,
      publishedAt: publishedAt || null,
      snippet: snippet || null,
    });
    if (out.length >= max) break;
  }
  // Important: this must be valid JSON on stdout (no stray characters).
  process.stdout.write(JSON.stringify(out, null, 2) + "\n");
}

main().catch((err) => {
  console.error(String(err?.stack || err));
  process.exit(2);
});
