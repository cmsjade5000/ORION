import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
import crypto from "node:crypto";
import os from "node:os";
import { spawn } from "node:child_process";
import express from "express";
import cors from "cors";
import { parseTelegramInitData, verifyTelegramInitData } from "./lib/telegram.js";
import { issueSseToken, verifySseToken } from "./lib/sse_token.js";
import { createFixedWindowLimiter } from "./lib/rate_limit.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.disable("x-powered-by");

const NODE_ENV = process.env.NODE_ENV || "development";
const IS_PROD = NODE_ENV === "production";

// Default to loopback to comply with SECURITY.md (no inbound exposure by default).
// For production hosting, set HOST=0.0.0.0 explicitly.
const HOST = process.env.HOST || "127.0.0.1";
const PORT = Number(process.env.PORT || 8787);

function parseAllowedOrigins() {
  const raw = String(process.env.MINIAPP_ALLOWED_ORIGINS || "").trim();
  const out = new Set();
  if (raw) {
    for (const part of raw.split(",")) {
      const s = part.trim();
      if (!s) continue;
      out.add(s);
    }
    return out;
  }

  // Default to the configured Mini App URL origin if present.
  const url = String(process.env.ORION_MINIAPP_URL || "").trim();
  if (url) {
    try {
      out.add(new URL(url).origin);
    } catch {
      // ignore
    }
  }

  return out;
}

const ALLOWED_ORIGINS = parseAllowedOrigins();
let corsWarned = false;

app.use(
  cors({
    origin: (origin, cb) => {
      // Same-origin requests often omit Origin; allow those.
      if (!origin) return cb(null, true);

      // If no allowlist is configured, keep CORS open (initData verification is the real gate).
      // In production, you should set MINIAPP_ALLOWED_ORIGINS to your app origin(s) anyway.
      if (ALLOWED_ORIGINS.size === 0) {
        if (IS_PROD && !corsWarned) {
          corsWarned = true;
          // eslint-disable-next-line no-console
          console.log("[miniapp] WARNING: MINIAPP_ALLOWED_ORIGINS not set; CORS is permissive.");
        }
        return cb(null, true);
      }

      if (ALLOWED_ORIGINS.has(origin)) return cb(null, true);
      return cb(null, false);
    },
    // We don't use cookies, but some embedded WebViews send credentials anyway.
    credentials: true,
  })
);

// If you later add POST endpoints.
app.use(express.json({ limit: "256kb" }));

app.set("trust proxy", 1);

// Basic security headers. Keep this conservative to avoid breaking Telegram WebViews.
app.use((req, res, next) => {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("Referrer-Policy", "no-referrer");
  res.setHeader("Permissions-Policy", "geolocation=(), microphone=(), camera=()");
  next();
});

function readFirstExistingFile(paths) {
  for (const p of paths) {
    try {
      if (p && fs.existsSync(p)) return fs.readFileSync(p, "utf8");
    } catch {
      // ignore
    }
  }
  return null;
}

function resolveTelegramBotToken() {
  const fromEnv = process.env.TELEGRAM_BOT_TOKEN?.trim();
  if (fromEnv) return fromEnv;

  const tokenFile =
    process.env.TELEGRAM_BOT_TOKEN_FILE?.trim() ||
    process.env.TELEGRAM_TOKEN_FILE?.trim() ||
    "";

  const fromFile = readFirstExistingFile([
    tokenFile,
    path.join(os.homedir(), ".openclaw", "secrets", "telegram.token"),
  ]);

  return fromFile?.trim() || "";
}

function extractTelegramContext(req) {
  const initData = req.header("x-telegram-init-data") || "";
  const raw = typeof initData === "string" ? initData : "";
  const trimmed = raw.trim();
  // Guard: initData should be small. Very large headers are suspicious / accidental.
  if (trimmed && trimmed.length > 8192) {
    return {
      initData: "",
      verified: false,
      params: null,
      userId: null,
      chatId: null,
      error: "too_large",
    };
  }
  if (!trimmed) {
    return {
      initData: "",
      verified: false,
      params: null,
      userId: null,
      chatId: null,
      error: "missing",
    };
  }

  const botToken = resolveTelegramBotToken();
  const maxAgeSec = Number(process.env.TELEGRAM_INITDATA_MAX_AGE_SEC || 24 * 60 * 60);
  if (!botToken) {
    return {
      initData: trimmed,
      verified: false,
      params: parseTelegramInitData(trimmed),
      userId: null,
      chatId: null,
      error: "no_bot_token",
    };
  }

  const v = verifyTelegramInitData({
    initData: trimmed,
    botToken,
    maxAgeSec,
    clockSkewSec: Number(process.env.TELEGRAM_INITDATA_CLOCK_SKEW_SEC || 60),
  });
  const params = v.params ?? null;

  let userId = null;
  let chatId = null;
  try {
    const user = params?.user ? JSON.parse(params.user) : null;
    if (user && typeof user.id === "number") userId = user.id;
  } catch {
    // ignore
  }
  try {
    const chat = params?.chat ? JSON.parse(params.chat) : null;
    if (chat && typeof chat.id === "number") chatId = chat.id;
  } catch {
    // ignore
  }

  return {
    initData: trimmed,
    verified: Boolean(v.ok),
    params,
    userId,
    chatId,
    error: v.ok ? null : v.error,
  };
}

function canAcceptUnverifiedInitData() {
  return process.env.ALLOW_UNVERIFIED_INITDATA === "1";
}

// Back-compat helper (some endpoints only care about the opaque string).
function extractTelegramInitData(req) {
  return extractTelegramContext(req).initData;
}

function createId(prefix) {
  // Node 18+ has crypto.randomUUID().
  const id = crypto.randomUUID ? crypto.randomUUID() : crypto.randomBytes(16).toString("hex");
  return `${prefix}_${id}`;
}

// Fail closed in production if key security knobs aren't set.
if (IS_PROD) {
  const sseSecret = String(process.env.SSE_TOKEN_SECRET || "").trim();
  if (!sseSecret || sseSecret === "dev-insecure-change-me") {
    throw new Error("[miniapp] SSE_TOKEN_SECRET must be set to a strong value in production.");
  }
  if (!String(process.env.INGEST_TOKEN || "").trim()) {
    throw new Error("[miniapp] INGEST_TOKEN must be set in production (prevents unauthenticated ingest).");
  }
}

// Keep this list in sync with the gateway agent roster (agents/INDEX.md).
// ORION is central and rendered separately; this list is the orbiting specialists.
const AGENTS = ["ATLAS", "EMBER", "PIXEL", "NODE", "LEDGER", "AEGIS"];
let tick = 0;
let commandIdx = 0;
let ledgerPulseIdx = 0;

const ACTIVITY_RULES = [
  { activity: "error", match: /(?:error|fail|failed|panic|broken|crash)/i },
  { activity: "search", match: /(?:search|find|lookup|research|scan)/i },
  { activity: "files", match: /(?:file|files|docs?|read|summarize|note|notes)/i },
  { activity: "tooling", match: /(?:tool|run|exec|execute|command|script|deploy|build)/i },
  { activity: "messaging", match: /(?:message|notify|send|email|ping|telegram)/i },
  { activity: "thinking", match: /(?:think|plan|analyz|strategy|reason|design)/i },
];

function normalizeText(text) {
  return String(text || "").trim();
}

function inferActivity(text) {
  const raw = normalizeText(text);
  if (!raw) return "idle";
  for (const rule of ACTIVITY_RULES) {
    if (rule.match.test(raw)) return rule.activity;
  }
  return "thinking";
}

// Sub-agents have their own activity emojis (on their node badges).
// ORION's central node should use *face* emojis only (exclusive) to reflect emotion/stance.
function orionFaceForActivity(activity) {
  switch (activity) {
    case "thinking":
      return "🤔";
    case "search":
      return "🧐";
    case "files":
      return "😎";
    case "tooling":
      return "😬";
    case "messaging":
      return "🙂";
    case "error":
      return "😵‍💫";
    default:
      return null;
  }
}

function orionFaceForTool(type) {
  switch (type) {
    case "tool.started":
      return "😬";
    case "tool.finished":
      return "😌";
    case "tool.failed":
      return "😵‍💫";
    default:
      return null;
  }
}

function orionFaceForTask(type) {
  switch (type) {
    case "task.started":
      return "😤";
    case "task.completed":
      return "😌";
    case "task.failed":
      return "😵‍💫";
    default:
      return null;
  }
}

function orionBadgeForActivity(activity) {
  switch (activity) {
    case "search":
      return "🔎";
    case "files":
      return "📁";
    case "tooling":
      return "🛠️";
    case "messaging":
      return "✉️";
    case "thinking":
      return "💭";
    case "error":
      return "⚠️";
    default:
      return null;
  }
}

function orionBadgeForTool(type) {
  switch (type) {
    case "tool.started":
      return "🛠️";
    case "tool.finished":
      return "✅";
    case "tool.failed":
      return "⚠️";
    default:
      return null;
  }
}

function orionBadgeForTask(type) {
  switch (type) {
    case "task.completed":
      return "✅";
    case "task.failed":
      return "⚠️";
    default:
      return null;
  }
}

function parseAgent(text) {
  const raw = normalizeText(text).toLowerCase();
  if (!raw) return null;
  for (const id of AGENTS) {
    const needle = id.toLowerCase();
    const re = new RegExp(`\\b${needle}\\b`, "i");
    if (re.test(raw)) return id;
  }
  return null;
}

function parseAgentSequence(text) {
  const raw = normalizeText(text).toLowerCase();
  if (!raw) return [];

  const hits = [];
  for (const id of AGENTS) {
    const needle = id.toLowerCase();
    const re = new RegExp(`\\b${needle}\\b`, "i");
    const idx = raw.search(re);
    if (idx >= 0) hits.push({ id, idx });
  }
  hits.sort((a, b) => a.idx - b.idx);

  // Preserve ordering by appearance, de-dupe.
  const out = [];
  const seen = new Set();
  for (const h of hits) {
    if (seen.has(h.id)) continue;
    seen.add(h.id);
    out.push(h.id);
  }
  return out;
}

function pickNextAgent() {
  commandIdx = (commandIdx + 1) % AGENTS.length;
  return AGENTS[commandIdx];
}

function buildMockLiveState() {
  // Simple deterministic animation so the UI shows motion.
  tick += 1;
  // Rotate through all agents, with a periodic "idle gap" where no agent is active.
  // Previous logic accidentally skipped ATLAS (index 0) because the same modulus was
  // used for the gap and the agent index.
  const phase = tick % (AGENTS.length + 1); // 0 => gap
  const activeAgentId = phase === 0 ? null : AGENTS[phase - 1];

  const agents = AGENTS.map((id) => {
    let status = "idle";
    if (activeAgentId === id) status = "active";
    else if (tick % 7 === 0 && id === "LEDGER") status = "busy";

    // Mock activity so the UI can show badges.
    // Later: ORION should emit a real activity type per agent from Task Packets / tools.
    let activity = "idle";
    if (status === "active") {
      const phase2 = tick % 4;
      activity = phase2 === 0 ? "thinking" : phase2 === 1 ? "search" : phase2 === 2 ? "files" : "tooling";
    } else if (status === "busy") {
      activity = "tooling";
    }

    return { id, status, activity };
  });

  return {
    ts: Date.now(),
    activeAgentId,
    agents,
    orion: {
      status: activeAgentId ? "busy" : "idle",
      processes: activeAgentId ? ["🧭"] : [],
    },
  };
}

// ---- In-memory runtime state (filled by /api/ingest) ----
// Fly can run multiple machines; this store is for *UI convenience* only.
// Once ORION emits real `state` snapshots, clients will recover via SSE + polling.
const STORE = createStore();
let lastIngestAt = 0;
let hasRealEvents = false;

function markRealEvent() {
  hasRealEvents = true;
  lastIngestAt = Date.now();
}

// Mock motion is now opt-in (off by default). Set MOCK_STATE=1 to enable.
const MOCK_STATE = process.env.MOCK_STATE === "1";

const INGEST_TOKEN = process.env.INGEST_TOKEN || "";
const STALE_MS = Number(process.env.STALE_MS || 20_000); // clear agent activity if no updates
const ACTIVE_STALE_MS = Number(process.env.ACTIVE_STALE_MS || 8_000); // clear ORION->agent focus line
const LINK_STALE_MS = Number(process.env.LINK_STALE_MS || 1_800); // how long to show directional flow
const AEGIS_ALARM_MS = Number(process.env.AEGIS_ALARM_MS || 30_000);
const AEGIS_WARN_MS = Number(process.env.AEGIS_WARN_MS || 0);

const ARTIFACT_TTL_MS = Number(process.env.ARTIFACT_TTL_MS || 60 * 60_000);
const MAX_ARTIFACTS = Number(process.env.MAX_ARTIFACTS || 24);
const ARTIFACTS_DIR = String(process.env.ARTIFACTS_DIR || path.join(os.tmpdir(), "orion-miniapp-artifacts")).trim();
try {
  fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });
} catch {
  // ignore (uploads will fail with a clear error)
}

const FEED_TTL_MS = Number(process.env.FEED_TTL_MS || 60 * 60_000);
const MAX_FEED_ITEMS = Number(process.env.MAX_FEED_ITEMS || 30);
const WORKFLOW_STALE_MS = Number(process.env.WORKFLOW_STALE_MS || 2 * 60_000);

const CONFIG_WARN =
  (process.env.SSE_TOKEN_SECRET || "") === "" ||
  (process.env.SSE_TOKEN_SECRET || "") === "dev-insecure-change-me" ||
  !resolveTelegramBotToken();

// Best-effort per-instance rate limits.
const RL_SSE_AUTH = createFixedWindowLimiter({ name: "sse_auth", windowMs: 60_000, max: 30 });
const RL_STATE = createFixedWindowLimiter({ name: "state", windowMs: 60_000, max: 120 });
const RL_COMMAND_IP = createFixedWindowLimiter({ name: "cmd_ip", windowMs: 60_000, max: 30 });
const RL_COMMAND_USER = createFixedWindowLimiter({ name: "cmd_user", windowMs: 60_000, max: 12 });
const RL_INGEST = createFixedWindowLimiter({ name: "ingest", windowMs: 10_000, max: 60 });

function createStore() {
  const agents = new Map();
  for (const id of AGENTS) {
    agents.set(id, {
      status: "idle",
      activity: "idle",
      updatedAt: 0,
    });
  }

  return {
    agents,
    activeAgentId: null,
    activeUpdatedAt: 0,
    orionBadges: new Map(), // emoji -> until
    link: { agentId: null, dir: "out", until: 0 },
    orionIo: { mode: null, until: 0 },
    orionBadge: { emoji: null, until: 0 },
    system: { alarmUntil: 0, warnUntil: 0 },
    artifacts: [], // newest-first
    artifactsById: new Map(), // id -> record
    feed: [], // newest-first
    feedById: new Map(), // id -> record
    workflow: null,
  };
}

function safeFilename(name) {
  const raw = String(name || "").trim() || "artifact";
  // Avoid path separators and control characters.
  const cleaned = raw
    .replace(/[\/\\\u0000-\u001f]+/g, "_")
    .replace(/["';]+/g, "_")
    .slice(0, 120)
    .trim();
  return cleaned || "artifact";
}

function extFor(mime, name) {
  const m = String(mime || "").toLowerCase();
  const n = String(name || "").toLowerCase();
  if (m === "application/pdf" || n.endsWith(".pdf")) return ".pdf";
  if (m === "text/plain" || n.endsWith(".txt")) return ".txt";
  if (m === "text/markdown" || n.endsWith(".md")) return ".md";
  if (m === "application/json" || n.endsWith(".json")) return ".json";
  if (m === "text/csv" || n.endsWith(".csv")) return ".csv";
  if (m === "application/zip" || m === "application/x-zip-compressed" || n.endsWith(".zip")) return ".zip";
  if (m === "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" || n.endsWith(".xlsx")) return ".xlsx";
  if (m === "application/vnd.ms-excel" || n.endsWith(".xls")) return ".xls";
  if (m.startsWith("audio/")) {
    if (n.endsWith(".mp3")) return ".mp3";
    if (n.endsWith(".wav")) return ".wav";
    if (n.endsWith(".m4a")) return ".m4a";
    if (n.endsWith(".ogg")) return ".ogg";
  }
  if (m.startsWith("video/")) {
    if (n.endsWith(".mp4")) return ".mp4";
    if (n.endsWith(".webm")) return ".webm";
    if (n.endsWith(".mov")) return ".mov";
  }
  if (m.startsWith("image/")) {
    const t = m.split("/")[1] || "img";
    if (/^[a-z0-9.+-]+$/.test(t)) return `.${t}`;
  }
  return "";
}

function escapePdfString(s) {
  // PDF literal string escaping for (), and backslash.
  return String(s || "").replace(/([()\\])/g, "\\$1");
}

function renderSimplePdfBytes(opts) {
  const title = String(opts?.title || "ORION Export").slice(0, 200);
  const body = String(opts?.body || "").slice(0, 600);
  const lines = [title, body].filter(Boolean);
  const content =
    "BT\n" +
    "/F1 18 Tf\n" +
    "72 740 Td\n" +
    lines.map((ln, i) => `${i === 0 ? "" : "0 -26 Td\n"}(${escapePdfString(ln)}) Tj\n`).join("") +
    "ET\n";

  const header = "%PDF-1.4\n%----\n";

  const obj1 = "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n";
  const obj2 = "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n";
  const obj3 =
    "3 0 obj\n" +
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> >>\n" +
    "endobj\n";
  const contentLen = Buffer.byteLength(content, "utf8");
  const obj4 = `4 0 obj\n<< /Length ${contentLen} >>\nstream\n${content}endstream\nendobj\n`;
  const obj5 = "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n";
  const objects = [obj1, obj2, obj3, obj4, obj5];

  // Byte offsets for xref. Object numbers are 1..N.
  const offsets = [0]; // entry 0 is the free object
  let offset = Buffer.byteLength(header, "utf8");
  for (const obj of objects) {
    offsets.push(offset);
    offset += Buffer.byteLength(obj, "utf8");
  }

  const startXref = offset;
  const xrefLines = [];
  xrefLines.push(`xref\n0 ${objects.length + 1}\n`);
  xrefLines.push("0000000000 65535 f \n");
  for (let i = 1; i <= objects.length; i += 1) {
    const off = String(offsets[i]).padStart(10, "0");
    xrefLines.push(`${off} 00000 n \n`);
  }

  const trailer =
    "trailer\n" +
    `<< /Size ${objects.length + 1} /Root 1 0 R >>\n` +
    "startxref\n" +
    `${startXref}\n` +
    "%%EOF\n";

  const pdf = header + objects.join("") + xrefLines.join("") + trailer;
  return Buffer.from(pdf, "utf8");
}

function inferPdfRequest(text) {
  const raw = String(text || "");
  if (!/\bpdf\b/i.test(raw)) return null;
  const m = raw.match(/\bpdf\b(?:\s+(?:of|for))?\s+["“](.+?)["”]/i) || raw.match(/\bpdf\b(?:\s+(?:of|for))?\s+(.{1,80})$/i);
  const subject = m && m[1] ? String(m[1]).trim() : "export";
  const base = safeFilename(subject).replace(/\s+/g, "_").slice(0, 48) || "export";
  return { name: `${base}.pdf`, title: `PDF: ${subject}` };
}

function pruneArtifacts(now = Date.now()) {
  const keep = [];
  for (const a of STORE.artifacts) {
    if (a && typeof a.expiresAt === "number" && a.expiresAt > now) {
      keep.push(a);
      continue;
    }

    if (a && a.id) STORE.artifactsById.delete(a.id);

    // Best-effort cleanup of on-disk files. (The in-memory store is ephemeral, but disk can grow.)
    const filePath = a && typeof a.filePath === "string" ? a.filePath : "";
    if (!filePath) continue;
    try {
      const abs = path.resolve(filePath);
      const root = path.resolve(ARTIFACTS_DIR) + path.sep;
      if (abs.startsWith(root) && fs.existsSync(abs)) fs.unlinkSync(abs);
    } catch {
      // ignore
    }
  }
  STORE.artifacts = keep.slice(0, MAX_ARTIFACTS);
}

function pruneFeed(now = Date.now()) {
  const keep = [];
  for (const it of STORE.feed) {
    if (it && typeof it.expiresAt === "number" && it.expiresAt > now) keep.push(it);
    else if (it && it.id) STORE.feedById.delete(it.id);
  }
  STORE.feed = keep.slice(0, MAX_FEED_ITEMS);
}

function addFeedItem(rec) {
  if (!rec || typeof rec.id !== "string") return null;
  pruneFeed(Date.now());
  STORE.feedById.set(rec.id, rec);
  STORE.feed = [rec, ...STORE.feed.filter((it) => it && it.id !== rec.id)].slice(0, MAX_FEED_ITEMS);
  return rec;
}

function setWorkflow(steps, { id } = {}) {
  const now = Date.now();
  const list = Array.isArray(steps) ? steps.filter((s) => typeof s === "string" && s.trim()).slice(0, 8) : [];
  if (list.length === 0) {
    STORE.workflow = null;
    return;
  }
  STORE.workflow = {
    id: String(id || createId("wf")),
    status: "running",
    steps: list.map((agentId) => ({ agentId, status: "pending" })),
    currentIndex: 0,
    updatedAt: now,
    until: now + WORKFLOW_STALE_MS,
  };
}

function touchWorkflow() {
  if (!STORE.workflow) return;
  const now = Date.now();
  STORE.workflow.updatedAt = now;
  STORE.workflow.until = now + WORKFLOW_STALE_MS;
}

function workflowIndexOf(agentId) {
  if (!STORE.workflow || !agentId) return -1;
  const steps = STORE.workflow.steps || [];
  return steps.findIndex((s) => s && s.agentId === agentId);
}

function workflowSetActive(agentId) {
  if (!STORE.workflow) return;
  const idx = workflowIndexOf(agentId);
  if (idx < 0) return;
  for (let i = 0; i < STORE.workflow.steps.length; i += 1) {
    const s = STORE.workflow.steps[i];
    if (!s) continue;
    if (i < idx && s.status === "pending") s.status = "done";
    if (i === idx) s.status = "active";
  }
  STORE.workflow.currentIndex = idx;
  STORE.workflow.status = "running";
  touchWorkflow();
}

function workflowSetDone(agentId, ok) {
  if (!STORE.workflow) return;
  const idx = workflowIndexOf(agentId);
  if (idx < 0) return;
  const s = STORE.workflow.steps[idx];
  if (s) s.status = ok ? "done" : "failed";

  // Advance pointer if the current step completed successfully.
  if (ok && STORE.workflow.currentIndex === idx) {
    STORE.workflow.currentIndex = Math.min(STORE.workflow.steps.length, idx + 1);
    const next = STORE.workflow.steps[STORE.workflow.currentIndex];
    if (next && next.status === "pending") {
      // leave it pending until it starts
    }
  }

  if (!ok) {
    STORE.workflow.status = "failed";
  } else {
    const allDone = STORE.workflow.steps.every((st) => st && st.status === "done");
    if (allDone) STORE.workflow.status = "completed";
  }
  touchWorkflow();
}

function addArtifactRecord(rec) {
  if (!rec || typeof rec.id !== "string") return null;
  pruneArtifacts(Date.now());
  STORE.artifactsById.set(rec.id, rec);
  // Newest-first list (dedupe).
  STORE.artifacts = [rec, ...STORE.artifacts.filter((a) => a && a.id !== rec.id)].slice(0, MAX_ARTIFACTS);
  return rec;
}

function simulatePdfArtifact({ text, agentId }) {
  const req = inferPdfRequest(text);
  if (!req) return null;

  const id = createId("art");
  const mime = "application/pdf";
  const bytes = renderSimplePdfBytes({ title: req.title, body: "Generated by ORION (simulated)." });

  let filePath;
  try {
    const ext = extFor(mime, req.name);
    filePath = path.join(ARTIFACTS_DIR, `${id}${ext || ".pdf"}`);
    fs.writeFileSync(filePath, bytes);
  } catch {
    return null;
  }

  const createdAt = Date.now();
  const rec = addArtifactRecord({
    id,
    kind: "file",
    name: req.name,
    mime,
    url: `/api/artifacts/${id}`,
    createdAt,
    expiresAt: createdAt + Math.max(10_000, ARTIFACT_TTL_MS),
    sizeBytes: bytes.length,
    agentId: agentId || null,
    filePath,
  });

  applyEventToStore({ type: "artifact.created", agentId: agentId || null, artifact: rec });
  scheduleStateBroadcast();
  return rec;
}

function setAgentStatus(id, status) {
  const a = STORE.agents.get(id);
  if (!a) return;
  a.status = status;
  a.updatedAt = Date.now();
}

function setAgentActivity(id, activity) {
  const a = STORE.agents.get(id);
  if (!a) return;
  a.activity = activity;
  a.updatedAt = Date.now();
}

function bumpActive(id) {
  if (!id) return;
  STORE.activeAgentId = id;
  STORE.activeUpdatedAt = Date.now();
}

function setLink(agentId, dir, holdMs = LINK_STALE_MS) {
  if (!agentId) return;
  const until = Date.now() + Math.max(250, holdMs);
  STORE.link.agentId = agentId;
  STORE.link.dir = dir === "in" ? "in" : "out";
  STORE.link.until = Math.max(STORE.link.until || 0, until);
}

function addOrionBadge(emoji, holdMs = 5200) {
  if (!emoji) return;
  STORE.orionBadges.set(emoji, Math.max(STORE.orionBadges.get(emoji) || 0, Date.now() + holdMs));
}

function setOrionIo(mode, holdMs = 2400) {
  if (mode !== "receiving" && mode !== "dispatching") return;
  STORE.orionIo.mode = mode;
  STORE.orionIo.until = Math.max(STORE.orionIo.until || 0, Date.now() + Math.max(300, holdMs));
}

function setOrionBadge(emoji, holdMs = 2400) {
  if (!emoji) return;
  STORE.orionBadge.emoji = emoji;
  STORE.orionBadge.until = Math.max(STORE.orionBadge.until || 0, Date.now() + Math.max(350, holdMs));
}

function applyEventToStore(body) {
  const type = typeof body?.type === "string" ? body.type : "";
  const agentId = typeof body?.agentId === "string" ? body.agentId : null;
  const activity = typeof body?.activity === "string" ? body.activity : null;

  if (type === "response.created") {
    const text = String(body?.text || body?.response?.text || "").trim();
    if (!text) return;
    const ts = typeof body?.ts === "number" ? body.ts : Date.now();
    const id = typeof body?.id === "string" ? body.id : createId("feed");
    addFeedItem({
      id,
      kind: "response",
      ts,
      icon: "💬",
      text: text.slice(0, 500),
      agentId,
      expiresAt: ts + Math.max(10_000, FEED_TTL_MS),
    });
    return;
  }

  if (type === "artifact.created") {
    const art = body?.artifact && typeof body.artifact === "object" ? body.artifact : null;
    const id = typeof art?.id === "string" ? art.id : createId("art");
    const name = safeFilename(art?.name);
    const mime = String(art?.mime || "application/octet-stream");
    const url = typeof art?.url === "string" ? art.url : `/api/artifacts/${id}`;
    const createdAt = typeof art?.createdAt === "number" ? art.createdAt : Date.now();
    const ttlMs = typeof art?.ttlMs === "number" ? art.ttlMs : ARTIFACT_TTL_MS;
    const expiresAt = createdAt + Math.max(10_000, Number(ttlMs) || 0);
    const sizeBytes = typeof art?.sizeBytes === "number" ? art.sizeBytes : null;
    const rec = addArtifactRecord({
      id,
      kind: "file",
      name,
      mime,
      url,
      createdAt,
      expiresAt,
      sizeBytes,
      agentId,
      // Optional server-local storage for uploaded artifacts.
      filePath: typeof art?.filePath === "string" ? art.filePath : null,
    });

    // Visual hint: treat artifacts as "return transmission".
    if (agentId) setLink(agentId, "in", 1400);
    setOrionIo("receiving", 1800);
    addOrionBadge("📎", 3800);
    setOrionBadge("✅", 2000);
    bumpActive(agentId || STORE.activeAgentId || "LEDGER");

    return rec;
  }

  // Allow ORION to push full snapshots in the future.
  if (type === "state" && body?.state && typeof body.state === "object") {
    const s = body.state;
    if (Array.isArray(s.agents)) {
      for (const a of s.agents) {
        if (!a || typeof a.id !== "string") continue;
        if (!STORE.agents.has(a.id)) continue;
        if (typeof a.status === "string") setAgentStatus(a.id, a.status);
        if (typeof a.activity === "string") setAgentActivity(a.id, a.activity);
      }
    }
    if (typeof s.activeAgentId === "string") bumpActive(s.activeAgentId);
    if (Array.isArray(s?.orion?.processes)) {
      for (const e of s.orion.processes) addOrionBadge(String(e), 2500);
    }
    return;
  }

  if (type === "agent.activity") {
    if (agentId) {
      if (activity === "idle") {
        setAgentActivity(agentId, "idle");
        setAgentStatus(agentId, "idle");
      } else {
        setAgentStatus(agentId, "active");
        if (activity) setAgentActivity(agentId, activity);
      }
      bumpActive(agentId);
      setLink(agentId, "out", LINK_STALE_MS);
    }
    // Mirror activity to the central node so the user can see what ORION is doing.
    const face = orionFaceForActivity(activity);
    if (face) addOrionBadge(face, 5200);
    const badge = orionBadgeForActivity(activity);
    if (badge) setOrionBadge(badge, 2600);
    return;
  }

  if (type === "tool.started" || type === "tool.finished" || type === "tool.failed") {
    const face = orionFaceForTool(type);
    if (face) addOrionBadge(face, 5200);
    const badge = orionBadgeForTool(type);
    if (badge) setOrionBadge(badge, 2600);
    if (agentId) {
      setAgentStatus(agentId, "busy");
      setAgentActivity(agentId, type === "tool.failed" ? "error" : "tooling");
      bumpActive(agentId);
      setLink(agentId, "out", LINK_STALE_MS);
    }

    if (type === "tool.failed") {
      STORE.system.alarmUntil = Math.max(STORE.system.alarmUntil || 0, Date.now() + AEGIS_ALARM_MS);
    } else if (type === "tool.started" && AEGIS_WARN_MS > 0) {
      STORE.system.warnUntil = Math.max(STORE.system.warnUntil || 0, Date.now() + AEGIS_WARN_MS);
    }
    return;
  }

  if (type.startsWith("task.")) {
    const face = orionFaceForTask(type);
    if (face) addOrionBadge(face, 5200);
    const badge = orionBadgeForTask(type);
    if (badge) setOrionBadge(badge, 3200);
    if (agentId) {
      if (type === "task.completed" || type === "task.failed") {
        // Conservative: mark idle at the end of a task unless later events say otherwise.
        setAgentActivity(agentId, "idle");
        setAgentStatus(agentId, "idle");
        // Show return-flow back into ORION.
        setOrionIo("receiving", 2200);
        setLink(agentId, "in", 1200);
      } else {
        setAgentStatus(agentId, "active");
        setLink(agentId, "out", LINK_STALE_MS);
        setOrionIo("dispatching", 1600);
      }
      bumpActive(agentId);
    }

    if (type === "task.failed") {
      STORE.system.alarmUntil = Math.max(STORE.system.alarmUntil || 0, Date.now() + AEGIS_ALARM_MS);
    }
    // Update workflow progress if present.
    if (type === "task.started") workflowSetActive(agentId);
    if (type === "task.completed") workflowSetDone(agentId, true);
    if (type === "task.failed") workflowSetDone(agentId, false);
  }
}

function snapshotLiveState() {
  const now = Date.now();
  pruneArtifacts(now);
  pruneFeed(now);
  if (STORE.workflow?.until && STORE.workflow.until <= now) STORE.workflow = null;
  const agents = AGENTS.map((id) => {
    const a = STORE.agents.get(id);
    if (!a) return { id, status: "idle", activity: "idle" };

    const stale = !a.updatedAt || now - a.updatedAt > STALE_MS;
    const status = stale ? "idle" : a.status;
    const activity = stale ? "idle" : a.activity;

    // AEGIS is a "system/remote" agent: show a semi-permanent badge.
    // Prefer alarming icons for recent failures.
    let badge = null;
    if (id === "AEGIS") {
      const alarm = STORE.system?.alarmUntil && STORE.system.alarmUntil > now;
      const warn = (STORE.system?.warnUntil && STORE.system.warnUntil > now) || CONFIG_WARN;
      badge = alarm ? "🚨" : warn ? "⚠️" : "🛰️";
    }

    return { id, status, activity, badge };
  });

  const activeAgentId =
    STORE.activeAgentId && STORE.activeUpdatedAt && now - STORE.activeUpdatedAt <= ACTIVE_STALE_MS
      ? STORE.activeAgentId
      : null;

  const link =
    STORE.link?.agentId && STORE.link.until && STORE.link.until > now
      ? { agentId: STORE.link.agentId, dir: STORE.link.dir }
      : null;

  // Keep only recent badges, prefer the most recent few.
  const badges = [];
  for (const [emoji, until] of STORE.orionBadges.entries()) {
    if (until > now) badges.push({ emoji, until });
  }
  badges.sort((a, b) => b.until - a.until);

  const io = STORE.orionIo?.until && STORE.orionIo.until > now ? STORE.orionIo.mode : null;
  const badge = STORE.orionBadge?.until && STORE.orionBadge.until > now ? STORE.orionBadge.emoji : null;
  const orionProcesses =
    badges.length === 0 && !activeAgentId && !io && !badge
      ? ["😴"] // Stable idle indicator when nothing is happening.
      : badges.slice(0, 3).map((b) => b.emoji);

  return {
    ts: now,
    activeAgentId,
    link,
    agents,
    orion: {
      status: activeAgentId || badges.length ? "busy" : "idle",
      processes: orionProcesses,
      badge,
      io,
    },
    artifacts: STORE.artifacts
      .filter((a) => a && a.expiresAt && a.expiresAt > now)
      .map((a) => ({
        id: a.id,
        kind: "file",
        name: a.name,
        mime: a.mime,
        url: a.url,
        createdAt: a.createdAt,
        sizeBytes: a.sizeBytes ?? null,
        agentId: a.agentId ?? null,
      })),
    feed: STORE.feed
      .filter((it) => it && it.expiresAt && it.expiresAt > now)
      .slice(0, 12)
      .map((it) => ({
        id: it.id,
        kind: it.kind,
        ts: it.ts,
        icon: it.icon ?? null,
        text: it.text,
        agentId: it.agentId ?? null,
      })),
    workflow: STORE.workflow
      ? {
          id: STORE.workflow.id,
          status: STORE.workflow.status,
          steps: (STORE.workflow.steps || []).map((s) => ({ agentId: s.agentId, status: s.status })),
          currentIndex: STORE.workflow.currentIndex || 0,
          updatedAt: STORE.workflow.updatedAt || now,
        }
      : null,
  };
}

function currentLiveState() {
  // Once real events arrive, stick with real snapshots (avoid reverting to mock loops).
  if (hasRealEvents) return snapshotLiveState();
  // If ORION has recently pushed events, prefer that.
  if (Date.now() - lastIngestAt < 30_000) return snapshotLiveState();
  // Otherwise keep the UI alive with mock motion until real wiring lands.
  if (MOCK_STATE) return buildMockLiveState();
  return snapshotLiveState();
}

// ---- SSE: token exchange + streaming ----
const STREAM_CLIENTS = new Set(); // Set<express.Response>
const STREAM_CLIENTS_BY_IP = new Map(); // ip -> count
const MAX_STREAM_CLIENTS = Number(process.env.MAX_STREAM_CLIENTS || 250);
const MAX_STREAM_CLIENTS_PER_IP = Number(process.env.MAX_STREAM_CLIENTS_PER_IP || 10);

// NOTE: Fly.io can run multiple machines; do not store auth tokens in memory.
// Instead we issue a short-lived, signed token that any machine can verify.
const SSE_TOKEN_SECRET = process.env.SSE_TOKEN_SECRET || "dev-insecure-change-me";

// ---- Artifacts (files created by ORION) ----
// Uploads are authenticated with INGEST_TOKEN (service-to-service).
// Downloads are authenticated with either:
// - `?token=` (same signed token format as SSE), or
// - verified Telegram initData header (XHR/fetch use-case).

app.post(
  "/api/artifacts",
  express.raw({ type: () => true, limit: String(process.env.ARTIFACT_UPLOAD_LIMIT || "16mb") }),
  (req, res) => {
    if (INGEST_TOKEN) {
      const auth = String(req.header("authorization") || "");
      if (auth !== `Bearer ${INGEST_TOKEN}`) {
        return res.status(401).json({ ok: false, error: { code: "UNAUTHORIZED", message: "Bad token" } });
      }
    } else if (IS_PROD) {
      return res.status(503).json({
        ok: false,
        error: { code: "MISCONFIGURED", message: "INGEST_TOKEN is required in production" },
      });
    }

    const buf = Buffer.isBuffer(req.body) ? req.body : Buffer.from([]);
    if (buf.length === 0) {
      return res.status(400).json({ ok: false, error: { code: "BAD_REQUEST", message: "Empty body" } });
    }

    const nameHeader = String(req.header("x-artifact-name") || "").trim();
    const mimeHeader = String(req.header("content-type") || "").trim();
    const agentId = String(req.header("x-agent-id") || req.query?.agentId || "").trim() || null;

    const id = createId("art");
    const nameBase = safeFilename(nameHeader || `artifact-${id}${extFor(mimeHeader, nameHeader)}`);
    const mime = mimeHeader || "application/octet-stream";

    const ext = extFor(mime, nameBase);
    const name = nameBase.endsWith(ext) ? nameBase : `${nameBase}${ext}`;

    let filePath;
    try {
      filePath = path.join(ARTIFACTS_DIR, `${id}${ext || ""}`);
      fs.writeFileSync(filePath, buf);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      return res.status(500).json({ ok: false, error: { code: "WRITE_FAILED", message: msg } });
    }

    markRealEvent();

    const createdAt = Date.now();
    const url = `/api/artifacts/${id}`;
    const rec = addArtifactRecord({
      id,
      kind: "file",
      name,
      mime,
      url,
      createdAt,
      expiresAt: createdAt + Math.max(10_000, ARTIFACT_TTL_MS),
      sizeBytes: buf.length,
      agentId,
      filePath,
    });

    // Mirror through the normal event path so clients update quickly.
    applyEventToStore({ type: "artifact.created", agentId, artifact: rec });
    scheduleStateBroadcast();

    res.setHeader("Cache-Control", "no-store");
    return res.json({ ok: true, artifact: { id, kind: "file", name, mime, url, createdAt, sizeBytes: buf.length, agentId } });
  }
);

app.get("/api/artifacts/:id", (req, res) => {
  const id = String(req.params?.id || "").trim();
  if (!id) {
    return res.status(400).json({ ok: false, error: { code: "BAD_REQUEST", message: "Missing id" } });
  }

  let allowed = false;
  const token = typeof req.query?.token === "string" ? req.query.token : "";
  if (token) {
    const v = verifySseToken({ token, secret: SSE_TOKEN_SECRET });
    allowed = Boolean(v.ok);
  } else {
    // Fetch/XHR fallback: allow verified initData (won't work for a plain link click).
    const ctx = extractTelegramContext(req);
    if (ctx.verified || canAcceptUnverifiedInitData()) allowed = true;
  }

  if (!allowed) {
    return res.status(401).json({
      ok: false,
      error: { code: "UNAUTHORIZED", message: "Missing/invalid token. Open from the Mini App or use a signed token." },
    });
  }

  pruneArtifacts(Date.now());
  const rec = STORE.artifactsById.get(id);
  if (!rec) {
    return res.status(404).json({ ok: false, error: { code: "NOT_FOUND", message: "Unknown artifact" } });
  }

  const filePath = typeof rec.filePath === "string" ? rec.filePath : "";
  if (!filePath) {
    return res.status(404).json({ ok: false, error: { code: "NOT_FOUND", message: "Artifact has no file payload" } });
  }

  const abs = path.resolve(filePath);
  const root = path.resolve(ARTIFACTS_DIR) + path.sep;
  if (!abs.startsWith(root)) {
    return res.status(403).json({ ok: false, error: { code: "FORBIDDEN", message: "Bad artifact path" } });
  }

  if (!fs.existsSync(abs)) {
    return res.status(404).json({ ok: false, error: { code: "NOT_FOUND", message: "File missing" } });
  }

  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Content-Type", rec.mime || "application/octet-stream");
  // Note: keep filename ASCII-ish; Telegram clients can be picky.
  const fname = safeFilename(rec.name || "artifact");
  res.setHeader("Content-Disposition", `attachment; filename=\"${fname}\"`);
  return res.sendFile(abs);
});

function sseWrite(res, event, data) {
  if (event) res.write(`event: ${event}\n`);
  res.write(`data: ${JSON.stringify(data)}\n\n`);
}

function sseBroadcast(event, data) {
  for (const res of STREAM_CLIENTS) {
    try {
      sseWrite(res, event, data);
    } catch {
      // ignore broken pipes; cleanup happens on close
    }
  }
}

app.post("/api/sse-auth", (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  const rl = RL_SSE_AUTH.hit(req.ip || "unknown");
  res.setHeader("X-RateLimit-Limit", String(rl.limit));
  res.setHeader("X-RateLimit-Remaining", String(rl.remaining));
  res.setHeader("X-RateLimit-Reset", String(Math.floor(rl.resetAt / 1000)));
  if (!rl.ok) {
    return res.status(429).json({ ok: false, error: { code: "RATE_LIMITED", message: "Too many requests" } });
  }

  const ctx = extractTelegramContext(req);
  if (!ctx.verified && !canAcceptUnverifiedInitData()) {
    return res.status(401).json({
      ok: false,
      error: {
        code: "UNAUTHORIZED",
        message: "Telegram initData not verified. Open via the bot Web App button and retry.",
      },
    });
  }

  const initDataSha256 = crypto.createHash("sha256").update(String(ctx.initData || "")).digest("hex");
  const { token, expiresAt } = issueSseToken({ initDataSha256, secret: SSE_TOKEN_SECRET });
  return res.json({ ok: true, token, expiresAt });
});

app.get("/api/events", (req, res) => {
  const token = typeof req.query?.token === "string" ? req.query.token : "";
  const v = verifySseToken({ token, secret: SSE_TOKEN_SECRET });
  if (!v.ok) {
    return res.status(401).json({
      ok: false,
      error: { code: "UNAUTHORIZED", message: `Invalid stream token (${v.error})` },
    });
  }

  if (STREAM_CLIENTS.size >= MAX_STREAM_CLIENTS) {
    return res.status(429).json({
      ok: false,
      error: { code: "RATE_LIMITED", message: "Too many active stream connections" },
    });
  }

  const ip = req.ip || "unknown";
  const curIp = STREAM_CLIENTS_BY_IP.get(ip) || 0;
  if (curIp >= MAX_STREAM_CLIENTS_PER_IP) {
    return res.status(429).json({
      ok: false,
      error: { code: "RATE_LIMITED", message: "Too many active streams from this IP" },
    });
  }

  res.status(200);
  res.setHeader("Content-Type", "text/event-stream; charset=utf-8");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("X-Accel-Buffering", "no");
  if (typeof res.flushHeaders === "function") res.flushHeaders();

  // Initial snapshot
  sseWrite(res, "state", currentLiveState());

  STREAM_CLIENTS.add(res);
  STREAM_CLIENTS_BY_IP.set(ip, curIp + 1);

  const keepAlive = setInterval(() => {
    try {
      res.write(`: keepalive ${Date.now()}\n\n`);
    } catch {
      // ignored
    }
  }, 15_000);

  req.on("close", () => {
    clearInterval(keepAlive);
    STREAM_CLIENTS.delete(res);
    const n = (STREAM_CLIENTS_BY_IP.get(ip) || 1) - 1;
    if (n <= 0) STREAM_CLIENTS_BY_IP.delete(ip);
    else STREAM_CLIENTS_BY_IP.set(ip, n);
  });
});

let stateBroadcastScheduled = false;
function scheduleStateBroadcast() {
  if (stateBroadcastScheduled) return;
  stateBroadcastScheduled = true;
  setTimeout(() => {
    stateBroadcastScheduled = false;
    if (STREAM_CLIENTS.size === 0) return;
    sseBroadcast("state", currentLiveState());
  }, 120);
}

// Broadcast new state periodically (push model).
setInterval(() => {
  if (STREAM_CLIENTS.size === 0) return;
  sseBroadcast("state", currentLiveState());
}, 900);

app.get("/api/state", (req, res) => {
  const ctx = extractTelegramContext(req);
  const rl = RL_STATE.hit(req.ip || "unknown");
  res.setHeader("X-RateLimit-Limit", String(rl.limit));
  res.setHeader("X-RateLimit-Remaining", String(rl.remaining));
  res.setHeader("X-RateLimit-Reset", String(Math.floor(rl.resetAt / 1000)));
  if (!rl.ok) {
    return res.status(429).json({ ok: false, error: { code: "RATE_LIMITED", message: "Too many requests" } });
  }

  if (!ctx.verified && !canAcceptUnverifiedInitData()) {
    return res.status(401).json({
      ok: false,
      error: {
        code: "UNAUTHORIZED",
        message: "Telegram initData not verified. Open via the bot Web App button to view state.",
      },
    });
  }

  const live = currentLiveState();
  const out = { ...live };
  // Avoid leaking initData or internal verification hints in production responses.
  if (!IS_PROD) {
    out.debug = {
      initDataPresent: Boolean(ctx.initData),
      initDataLen: ctx.initData.length,
      initDataVerified: ctx.verified,
      initDataError: ctx.error,
    };
  }
  res.setHeader("Cache-Control", "no-store");
  res.json(out);
});

/**
 * ORION -> Mini App ingest (v0).
 *
 * ORION will POST event frames here; the server re-broadcasts to SSE clients and
 * updates an in-memory store that feeds the `state` snapshots.
 *
 * Auth: `Authorization: Bearer ${INGEST_TOKEN}`
 * NOTE: do not use Telegram initData for service-to-service auth.
 */
app.post("/api/ingest", (req, res) => {
  const rl = RL_INGEST.hit(req.ip || "unknown");
  res.setHeader("X-RateLimit-Limit", String(rl.limit));
  res.setHeader("X-RateLimit-Remaining", String(rl.remaining));
  res.setHeader("X-RateLimit-Reset", String(Math.floor(rl.resetAt / 1000)));
  if (!rl.ok) {
    return res.status(429).json({ ok: false, error: { code: "RATE_LIMITED", message: "Too many requests" } });
  }

  if (INGEST_TOKEN) {
    const auth = String(req.header("authorization") || "");
    if (auth !== `Bearer ${INGEST_TOKEN}`) {
      return res.status(401).json({ ok: false, error: { code: "UNAUTHORIZED", message: "Bad token" } });
    }
  } else if (IS_PROD) {
    return res.status(503).json({
      ok: false,
      error: { code: "MISCONFIGURED", message: "INGEST_TOKEN is required in production" },
    });
  }

  const type = typeof req.body?.type === "string" ? req.body.type.trim() : "";
  if (!type) {
    return res.status(400).json({ ok: false, error: { code: "BAD_REQUEST", message: "Missing `type`" } });
  }

  markRealEvent();

  const eventId = createId("evt");
  const eventTs = typeof req.body?.ts === "number" ? req.body.ts : Date.now();

  // eslint-disable-next-line no-console
  console.log("[miniapp] /api/ingest", { type, eventId });

  // Update store for the snapshot layer.
  applyEventToStore({ ...req.body, type });

  // Broadcast the raw event for clients that want fine-grained handling.
  if (STREAM_CLIENTS.size > 0) {
    sseBroadcast(type, {
      id: eventId,
      ts: eventTs,
      type,
      data: req.body,
    });
    // Also schedule a snapshot so clients can recover from any missed fine-grained frames.
    scheduleStateBroadcast();
  }

  return res.json({ ok: true, accepted: { id: eventId, ts: eventTs } });
});

/**
 * Stub command ingestion endpoint.
 *
 * Contract (v0):
 * - Accept JSON `{ text: string, clientTs?: number, meta?: object }`
 * - Reads Telegram initData from `x-telegram-init-data`
 * - Returns an "accepted" envelope with ids for future correlation
 *
 * Later: this is where ORION will map user input -> task packets / sessions.
 */
app.post("/api/command", (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  const ctx = extractTelegramContext(req);
  const initData = ctx.initData;
  const text = typeof req.body?.text === "string" ? req.body.text.trim() : "";
  const clientTs = typeof req.body?.clientTs === "number" ? req.body.clientTs : null;

  // Rate limit (best-effort). Prefer Telegram userId when verified, else fall back to IP.
  const ip = req.ip || "unknown";
  const rlIp = RL_COMMAND_IP.hit(ip);
  if (!rlIp.ok) {
    return res.status(429).json({ ok: false, error: { code: "RATE_LIMITED", message: "Too many commands" } });
  }
  if (ctx.verified && typeof ctx.userId === "number") {
    const rlUser = RL_COMMAND_USER.hit(String(ctx.userId));
    if (!rlUser.ok) {
      return res.status(429).json({ ok: false, error: { code: "RATE_LIMITED", message: "Slow down a bit" } });
    }
  }

  if (!text) {
    return res.status(400).json({
      ok: false,
      error: { code: "BAD_REQUEST", message: "Missing `text`" },
    });
  }

  if (text.length > 2000) {
    return res.status(400).json({
      ok: false,
      error: { code: "BAD_REQUEST", message: "`text` too long" },
    });
  }

  const requestId = createId("cmdreq");
  const acceptedId = createId("cmd");

  if (!ctx.verified && !canAcceptUnverifiedInitData()) {
    // eslint-disable-next-line no-console
    console.log("[miniapp] /api/command rejected", {
      requestId,
      initDataPresent: Boolean(initData),
      initDataLen: initData.length,
      initDataError: ctx.error,
    });
    return res.status(401).json({
      ok: false,
      error: {
        code: "UNAUTHORIZED",
        message:
          "Telegram initData not verified. Configure TELEGRAM_BOT_TOKEN (or TELEGRAM_BOT_TOKEN_FILE) on the server and retry from inside Telegram.",
      },
      debug: { initDataPresent: Boolean(initData), initDataLen: initData.length, initDataError: ctx.error },
    });
  }

  // SECURITY NOTE:
  // `initData` contains signed Telegram context and user identifiers; treat it as sensitive.
  // Avoid logging user-supplied command text in full (it can include secrets).
  // eslint-disable-next-line no-console
  console.log("[miniapp] /api/command accepted", {
    requestId,
    acceptedId,
    textLen: text.length,
    textPreview: text.slice(0, 120),
    initDataVerified: ctx.verified,
    initDataLen: initData.length,
    clientTs,
  });

  // Wire commands into the live state so nodes light up immediately.
  const targets = parseAgentSequence(text);
  const targetAgent = (targets[0] ?? parseAgent(text) ?? pickNextAgent());
  const activity = inferActivity(text);
  markRealEvent();

  // Visual: ORION is dispatching work outwards (faces only).
  addOrionBadge("😤", 2600);
  setOrionIo("dispatching", 2000);
  setOrionBadge(orionBadgeForActivity(activity) || "💭", 2000);

  const sequence = targets.length ? targets : [targetAgent];
  setWorkflow(sequence, { id: acceptedId });

  // Kick the first hop immediately so the UI responds to "send".
  const startHop = (agentId) => {
    applyEventToStore({ type: "task.started", agentId });

    if (agentId === "LEDGER") {
      ledgerPulseIdx += 1;
    }

    if (agentId === "LEDGER" && ledgerPulseIdx % 4 === 0) {
      applyEventToStore({ type: "tool.started", agentId });
    } else {
      applyEventToStore({ type: "agent.activity", agentId, activity });
    }
  };
  startHop(sequence[0]);

  if (STREAM_CLIENTS.size > 0) {
    sseBroadcast("command.accepted", {
      requestId,
      acceptedId,
      receivedAt: Date.now(),
      targetAgent: sequence[0],
      activity,
      // Avoid pushing initData to clients.
      textPreview: text.slice(0, 120),
    });
    scheduleStateBroadcast();
  }

  // Optional: route the command into ORION via OpenClaw (local-first).
  // Best-effort; deployments without OpenClaw installed can leave this off.
  // Security: never route (deliver) based on unverified initData, even in dev mode.
  const shouldRoute = process.env.OPENCLAW_ROUTE_COMMANDS === "1" && ctx.verified;
  // Prefer DM replies (userId) to avoid spamming groups when a miniapp is opened from a group context.
  const deliverTargetRaw = ctx.verified ? String(ctx.userId ?? ctx.chatId ?? "").trim() : "";
  const deliverTarget = /^[0-9]+$/.test(deliverTargetRaw) ? deliverTargetRaw : "";

  const shouldSimulateReply = !shouldRoute || !deliverTarget;
  const shouldSimulateWorkflow = shouldSimulateReply || sequence.length > 1;

  // Simulated hop progression:
  // - When not routing, this is the primary demo behavior (including a fake reply/artifact).
  // - When routing, this is *visual only* for multi-hop commands so the user can see the intended workflow
  //   even before ORION emits real task events back into /api/ingest.
  if (shouldSimulateWorkflow) {
    // Theatric pacing (human-observable). Override with env if desired.
    const hopMs = Number(process.env.SIM_HOP_MS || 1800);
    const gapMs = Number(process.env.SIM_GAP_MS || 800);

    const completeHop = (agentId) => {
      applyEventToStore({ type: "task.completed", agentId });
      if (STREAM_CLIENTS.size > 0) {
        sseBroadcast("task.completed", {
          id: acceptedId,
          ts: Date.now(),
          type: "task.completed",
          data: { requestId, ok: true, code: 0, agentId, simulated: true },
        });
        scheduleStateBroadcast();
      }
    };

    const run = (i) => {
      if (i >= sequence.length) return;
      const agentId = sequence[i];
      // We already started hop 0 above.
      if (i > 0) {
        // Visual: ORION dispatches each hop.
        addOrionBadge("😤", 1800);
        setOrionIo("dispatching", 1400);
        setOrionBadge(orionBadgeForActivity(activity) || "💭", 1400);
        startHop(agentId);
        if (STREAM_CLIENTS.size > 0) scheduleStateBroadcast();
      }

      setTimeout(() => {
        completeHop(agentId);
        // The last hop shouldn't linger longer than earlier hops (which get overwritten
        // by the next dispatch). Cap the final return-link duration.
        if (i === sequence.length - 1) {
          setLink(agentId, "in", gapMs + 200);
          if (shouldSimulateReply) {
            // Demo behavior: if the user asked for a PDF, produce a small simulated PDF
            // and surface it as a floating artifact bubble in the Mini App.
            simulatePdfArtifact({ text, agentId });
            // Demo behavior: surface a short simulated response in the in-app feed so
            // live Telegram testing is useful even before ORION routing is wired.
            const flat = String(text || "").replace(/\s+/g, " ").trim();
            const preview = flat.length > 220 ? `${flat.slice(0, 220)}…` : flat;
            applyEventToStore({
              type: "response.created",
              agentId: "ORION",
              text: preview ? `Simulated reply: received "${preview}"` : "Simulated reply: received.",
            });
            if (STREAM_CLIENTS.size > 0) scheduleStateBroadcast();
          }
        }
        setTimeout(() => run(i + 1), gapMs);
      }, hopMs);
    };

    run(0);
  }

  if (shouldRoute && deliverTarget) {
    const agentId = process.env.OPENCLAW_AGENT_ID?.trim() || "main";
    const args = [
      "agent",
      "--agent",
      agentId,
      "--message",
      text,
      "--deliver",
      "--channel",
      "telegram",
      "--reply-channel",
      "telegram",
      "--reply-to",
      deliverTarget,
      "--json",
    ];

    const shortText = (s) => {
      const raw = String(s || "").trim();
      const flat = raw.replace(/```/g, "").replace(/\s+/g, " ").trim();
      if (!flat) return "";
      if (flat.length <= 320) return flat;
      return `${flat.slice(0, 320)}…`;
    };

    const extractReplyText = (stdoutRaw) => {
      const s = String(stdoutRaw || "").trim();
      if (!s) return "";

      // Try parse JSON (OpenClaw --json).
      const tryParse = (candidate) => {
        try {
          return JSON.parse(candidate);
        } catch {
          return null;
        }
      };

      let obj = tryParse(s);
      if (!obj) {
        // Sometimes there are logs before/after JSON; try a substring.
        const first = s.indexOf("{");
        const last = s.lastIndexOf("}");
        if (first >= 0 && last > first) obj = tryParse(s.slice(first, last + 1));
      }

      const pick = (v) => (typeof v === "string" ? v : "");
      if (obj && typeof obj === "object") {
        // Heuristic: chase common shapes without assuming a fixed schema.
        const candidates = [
          pick(obj.reply?.text),
          pick(obj.reply?.message),
          pick(obj.reply?.content),
          pick(obj.result?.reply?.text),
          pick(obj.result?.reply?.message),
          pick(obj.output?.text),
          pick(obj.text),
        ].filter(Boolean);
        if (candidates.length) return candidates[0];
      }

      // Fallback: show the raw stdout (trimmed).
      return s;
    };

    try {
      const child = spawn("openclaw", args, {
        stdio: ["ignore", "pipe", "pipe"],
        env: process.env,
      });

      const MAX_LOG_BYTES = Number(process.env.OPENCLAW_ROUTE_MAX_LOG_BYTES || 64 * 1024);
      let out = "";
      let err = "";
      const push = (target, chunk) => {
        const next = target + chunk;
        if (next.length <= MAX_LOG_BYTES) return next;
        return next.slice(0, MAX_LOG_BYTES);
      };

      child.stdout.on("data", (d) => {
        out = push(out, d.toString("utf8"));
      });
      child.stderr.on("data", (d) => {
        err = push(err, d.toString("utf8"));
      });

      const timeoutMs = Number(process.env.OPENCLAW_ROUTE_TIMEOUT_MS || 45_000);
      const killTimer = setTimeout(() => {
        try {
          child.kill("SIGKILL");
        } catch {
          // ignore
        }
      }, Math.max(5_000, timeoutMs));

      child.on("error", (e) => {
        clearTimeout(killTimer);
        // eslint-disable-next-line no-console
        console.log("[miniapp] openclaw spawn failed", { message: e?.message || String(e) });
        applyEventToStore({ type: "task.failed", agentId: targetAgent });
        if (STREAM_CLIENTS.size > 0) {
          sseBroadcast("task.failed", {
            id: acceptedId,
            ts: Date.now(),
            type: "task.failed",
            data: { requestId, ok: false, code: null, agentId: targetAgent, error: e?.message || String(e) },
          });
          scheduleStateBroadcast();
        }
      });
      child.on("close", (code) => {
        clearTimeout(killTimer);
        const ok = code === 0;
        const preview = (ok ? out : err).trim().slice(0, 600);
        // eslint-disable-next-line no-console
        console.log("[miniapp] openclaw route result", { ok, code, preview });

        // Treat completion as a return-flow back into ORION.
        applyEventToStore({ type: ok ? "task.completed" : "task.failed", agentId: targetAgent });
        // Surface a short in-app response. (Telegram delivery still happens via --deliver.)
        const replyText = ok ? extractReplyText(out) : err;
        const short = shortText(replyText);
        if (short) applyEventToStore({ type: "response.created", agentId: "ORION", text: short });
        if (STREAM_CLIENTS.size > 0) {
          sseBroadcast(ok ? "task.completed" : "task.failed", {
            id: acceptedId,
            ts: Date.now(),
            type: ok ? "task.completed" : "task.failed",
            data: { requestId, ok, code, agentId: targetAgent },
          });
          scheduleStateBroadcast();
        }
      });
    } catch (e) {
      // eslint-disable-next-line no-console
      console.log("[miniapp] openclaw route exception", { message: (e && e.message) || String(e) });
      applyEventToStore({ type: "task.failed", agentId: targetAgent });
      if (STREAM_CLIENTS.size > 0) {
        sseBroadcast("task.failed", {
          id: acceptedId,
          ts: Date.now(),
          type: "task.failed",
          data: { requestId, ok: false, code: null, agentId: targetAgent, error: (e && e.message) || String(e) },
        });
        scheduleStateBroadcast();
      }
    }
  }

  return res.status(202).json({
    ok: true,
    status: "accepted",
    requestId,
    accepted: {
      id: acceptedId,
      receivedAt: Date.now(),
    },
    routing: {
      // Placeholder: ORION will eventually produce concrete IDs (task packet, session, etc.)
      target: "ORION",
      mode: "task_packet",
      taskPacketId: null,
      sessionId: null,
    },
  });
});

// Serve the Vite build in production (single deployable service).
// In dev, Vite serves the frontend on :5173 so we avoid requiring `dist/` here.
const distDir = path.resolve(__dirname, "../dist");
const distIndex = path.join(distDir, "index.html");
const shouldServeStatic =
  process.env.NODE_ENV === "production" && fs.existsSync(distIndex);

if (shouldServeStatic) {
  // Avoid Telegram/WebView caching a stale index.html (which would pin an old JS bundle).
  // Hashed assets can be cached aggressively; index.html should be no-store.
  app.use(
    express.static(distDir, {
      setHeaders: (res, filePath) => {
        const p = String(filePath || "");
        if (p.endsWith(`${path.sep}index.html`)) {
          res.setHeader("Cache-Control", "no-store");
          return;
        }
        // Vite fingerprints assets (content hash in filename), so long caching is safe.
        if (p.includes(`${path.sep}assets${path.sep}`)) {
          res.setHeader("Cache-Control", "public, max-age=31536000, immutable");
          return;
        }
        // Conservative default for other static files.
        res.setHeader("Cache-Control", "no-cache");
      },
    })
  );
  app.get("*", (req, res) => {
    res.setHeader("Cache-Control", "no-store");
    res.sendFile(distIndex);
  });
}

app.listen(PORT, HOST, () => {
  // eslint-disable-next-line no-console
  console.log(`[miniapp] listening on http://${HOST}:${PORT}`);
});
