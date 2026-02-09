#!/usr/bin/env node
/**
 * Tiny helper to POST events into the Mini App backend (/api/ingest).
 *
 * Usage:
 *   INGEST_URL=http://127.0.0.1:8787/api/ingest INGEST_TOKEN=... \
 *     node scripts/push_ingest.mjs agent.activity ATLAS search
 *
 * Or send raw JSON:
 *   echo '{"type":"task.routed","agentId":"EMBER","task":{"id":"tp_1"}}' | node scripts/push_ingest.mjs
 */

import process from "node:process";

const INGEST_URL = process.env.INGEST_URL || "http://127.0.0.1:8787/api/ingest";
const INGEST_TOKEN = process.env.INGEST_TOKEN || "";

function usage() {
  // eslint-disable-next-line no-console
  console.log(
    [
      "push_ingest.mjs",
      "",
      "Examples:",
      "  node scripts/push_ingest.mjs agent.activity ATLAS search",
      "  node scripts/push_ingest.mjs tool.started PIXEL tooling",
      "  echo '{\"type\":\"task.started\",\"agentId\":\"EMBER\",\"task\":{\"id\":\"tp_1\"}}' | node scripts/push_ingest.mjs",
      "",
      "Env:",
      "  INGEST_URL   (default http://127.0.0.1:8787/api/ingest)",
      "  INGEST_TOKEN (optional; required in production)",
    ].join("\n")
  );
}

async function readStdin() {
  if (process.stdin.isTTY) return "";
  const chunks = [];
  for await (const c of process.stdin) chunks.push(Buffer.from(c));
  return Buffer.concat(chunks).toString("utf8").trim();
}

const stdin = await readStdin();

let payload = null;
if (stdin) {
  try {
    payload = JSON.parse(stdin);
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error("stdin JSON parse failed:", err?.message || String(err));
    process.exit(2);
  }
} else {
  const [type, agentId, activityOrTool] = process.argv.slice(2);
  if (!type) {
    usage();
    process.exit(1);
  }
  payload = { type, ts: Date.now() };
  if (agentId) payload.agentId = agentId;
  if (type === "agent.activity" && activityOrTool) payload.activity = activityOrTool;
  if (type.startsWith("tool.") && activityOrTool) payload.tool = { name: activityOrTool };
}

const headers = { "content-type": "application/json" };
if (INGEST_TOKEN) headers.authorization = `Bearer ${INGEST_TOKEN}`;

const res = await fetch(INGEST_URL, { method: "POST", headers, body: JSON.stringify(payload) });
const txt = await res.text();
// eslint-disable-next-line no-console
console.log(res.status, txt);

