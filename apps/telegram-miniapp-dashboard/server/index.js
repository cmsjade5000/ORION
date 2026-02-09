import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";
import crypto from "node:crypto";
import os from "node:os";
import { spawn } from "node:child_process";
import express from "express";
import cors from "cors";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();

// Default to loopback to comply with SECURITY.md (no inbound exposure by default).
// For production hosting, set HOST=0.0.0.0 explicitly.
const HOST = process.env.HOST || "127.0.0.1";
const PORT = Number(process.env.PORT || 8787);

app.use(
  cors({
    origin: true,
    credentials: true,
  })
);

// If you later add POST endpoints.
app.use(express.json({ limit: "256kb" }));

app.set("trust proxy", 1);

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

function parseTelegramInitData(initData) {
  const params = new URLSearchParams(String(initData || ""));
  const out = {};
  for (const [k, v] of params.entries()) out[k] = v;
  return out;
}

function verifyTelegramInitData({ initData, botToken, maxAgeSec }) {
  const params = parseTelegramInitData(initData);
  const hashRaw = typeof params.hash === "string" ? params.hash : "";
  const hash = hashRaw.trim().toLowerCase();
  if (!hash) return { ok: false, error: "missing_hash", params };

  const pairs = [];
  for (const [k, v] of Object.entries(params)) {
    if (k === "hash") continue;
    pairs.push([k, String(v)]);
  }
  pairs.sort((a, b) => a[0].localeCompare(b[0]));
  const dataCheckString = pairs.map(([k, v]) => `${k}=${v}`).join("\n");

  // Telegram Mini App (WebApp) verification:
  // secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
  // Ref: https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
  const secretKey = crypto
    .createHmac("sha256", "WebAppData")
    .update(String(botToken))
    .digest();
  const computed = crypto
    .createHmac("sha256", secretKey)
    .update(dataCheckString)
    .digest("hex");

  const safeEq =
    computed.length === hash.length &&
    crypto.timingSafeEqual(Buffer.from(computed, "utf8"), Buffer.from(hash, "utf8"));
  if (!safeEq) return { ok: false, error: "bad_sig", params };

  const authDate = Number.parseInt(String(params.auth_date || ""), 10);
  if (Number.isFinite(authDate) && authDate > 0 && Number.isFinite(maxAgeSec) && maxAgeSec > 0) {
    const ageSec = Math.floor(Date.now() / 1000) - authDate;
    if (ageSec > maxAgeSec) return { ok: false, error: "expired", params };
  }

  return { ok: true, params };
}

function extractTelegramContext(req) {
  const initData = req.header("x-telegram-init-data") || "";
  const raw = typeof initData === "string" ? initData : "";
  const trimmed = raw.trim();
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

  const v = verifyTelegramInitData({ initData: trimmed, botToken, maxAgeSec });
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

const AGENTS = ["ATLAS", "EMBER", "PIXEL", "AEGIS", "LEDGER"];
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

function activityToEmoji(activity) {
  switch (activity) {
    case "thinking":
      return "🧠";
    case "search":
      return "🔎";
    case "files":
      return "📁";
    case "tooling":
      return "🛠️";
    case "messaging":
      return "✉️";
    case "error":
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

// Keep mock motion by default until ORION begins pushing real events.
// Set MOCK_STATE=0 in production once ORION is streaming.
const MOCK_STATE = process.env.MOCK_STATE !== "0";

const INGEST_TOKEN = process.env.INGEST_TOKEN || "";
const STALE_MS = Number(process.env.STALE_MS || 20_000); // clear agent activity if no updates
const ACTIVE_STALE_MS = Number(process.env.ACTIVE_STALE_MS || 8_000); // clear ORION->agent focus line
const LINK_STALE_MS = Number(process.env.LINK_STALE_MS || 4_200); // how long to show directional flow

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
  };
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

function applyEventToStore(body) {
  const type = typeof body?.type === "string" ? body.type : "";
  const agentId = typeof body?.agentId === "string" ? body.agentId : null;
  const activity = typeof body?.activity === "string" ? body.activity : null;

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
      setLink(agentId, "out");
    }
    // Mirror activity to the central node so the user can see what ORION is doing.
    const em = activityToEmoji(activity);
    if (em) addOrionBadge(em, 5200);
    return;
  }

  if (type === "tool.started" || type === "tool.finished" || type === "tool.failed") {
    addOrionBadge("🛠️", 5200);
    if (agentId) {
      setAgentStatus(agentId, "busy");
      setAgentActivity(agentId, type === "tool.failed" ? "error" : "tooling");
      bumpActive(agentId);
      setLink(agentId, "out");
    }
    return;
  }

  if (type.startsWith("task.")) {
    addOrionBadge("🧭", 5200);
    if (agentId) {
      if (type === "task.completed" || type === "task.failed") {
        // Conservative: mark idle at the end of a task unless later events say otherwise.
        setAgentActivity(agentId, "idle");
        setAgentStatus(agentId, "idle");
        // Show return-flow back into ORION.
        addOrionBadge("📥", 5200);
        setLink(agentId, "in", LINK_STALE_MS);
      } else {
        setAgentStatus(agentId, "active");
        setLink(agentId, "out");
      }
      bumpActive(agentId);
    }
  }
}

function snapshotLiveState() {
  const now = Date.now();
  const agents = AGENTS.map((id) => {
    const a = STORE.agents.get(id);
    if (!a) return { id, status: "idle", activity: "idle" };

    const stale = !a.updatedAt || now - a.updatedAt > STALE_MS;
    const status = stale ? "idle" : a.status;
    const activity = stale ? "idle" : a.activity;
    return { id, status, activity };
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

  return {
    ts: now,
    activeAgentId,
    link,
    agents,
    orion: {
      status: activeAgentId || badges.length ? "busy" : "idle",
      processes: badges.slice(0, 3).map((b) => b.emoji),
    },
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

// NOTE: Fly.io can run multiple machines; do not store auth tokens in memory.
// Instead we issue a short-lived, signed token that any machine can verify.
const SSE_TOKEN_SECRET = process.env.SSE_TOKEN_SECRET || "dev-insecure-change-me";

function b64urlEncode(buf) {
  return Buffer.from(buf).toString("base64url");
}

function b64urlDecode(s) {
  return Buffer.from(String(s), "base64url").toString("utf8");
}

function issueSseToken(initData) {
  // This token is only an initData *privacy* measure (keeps initData out of URLs).
  // It is not a substitute for verifying initData server-side.
  const now = Date.now();
  const payload = {
    iat: now,
    // 10 minutes: long enough for EventSource retries, short enough to limit leakage.
    exp: now + 10 * 60_000,
    // Bind the token to the initData contents (prevents token reuse across users).
    initDataSha256: crypto.createHash("sha256").update(String(initData || "")).digest("hex"),
  };
  const payloadJson = JSON.stringify(payload);
  const payloadB64 = b64urlEncode(payloadJson);
  const sig = crypto.createHmac("sha256", SSE_TOKEN_SECRET).update(payloadB64).digest();
  const sigB64 = b64urlEncode(sig);
  return { token: `${payloadB64}.${sigB64}`, expiresAt: payload.exp };
}

function verifySseToken(token) {
  const parts = String(token || "").split(".");
  if (parts.length !== 2) return { ok: false, error: "bad_format" };
  const [payloadB64, sigB64] = parts;
  const sig = Buffer.from(sigB64, "base64url");
  const expected = crypto.createHmac("sha256", SSE_TOKEN_SECRET).update(payloadB64).digest();
  if (sig.length !== expected.length || !crypto.timingSafeEqual(sig, expected)) {
    return { ok: false, error: "bad_sig" };
  }
  let payload;
  try {
    payload = JSON.parse(b64urlDecode(payloadB64));
  } catch {
    return { ok: false, error: "bad_payload" };
  }
  if (!payload || typeof payload.exp !== "number" || payload.exp <= Date.now()) {
    return { ok: false, error: "expired" };
  }
  if (typeof payload.initDataSha256 !== "string" || payload.initDataSha256.length < 16) {
    return { ok: false, error: "bad_claims" };
  }
  return { ok: true, payload };
}

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
  const ctx = extractTelegramContext(req);
  const initData = ctx.verified || canAcceptUnverifiedInitData() ? ctx.initData : "";
  const { token, expiresAt } = issueSseToken(initData);
  return res.json({ ok: true, token, expiresAt });
});

app.get("/api/events", (req, res) => {
  const token = typeof req.query?.token === "string" ? req.query.token : "";
  const v = verifySseToken(token);
  if (!v.ok) {
    return res.status(401).json({
      ok: false,
      error: { code: "UNAUTHORIZED", message: `Invalid stream token (${v.error})` },
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
  const live = currentLiveState();

  res.json({
    ...live,
    // Helpful for debugging; remove once verification is implemented.
    debug: {
      initDataPresent: Boolean(ctx.initData),
      initDataLen: ctx.initData.length,
      initDataVerified: ctx.verified,
      initDataError: ctx.error,
    },
  });
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
  if (INGEST_TOKEN) {
    const auth = String(req.header("authorization") || "");
    if (auth !== `Bearer ${INGEST_TOKEN}`) {
      return res.status(401).json({ ok: false, error: { code: "UNAUTHORIZED", message: "Bad token" } });
    }
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
  const ctx = extractTelegramContext(req);
  const initData = ctx.initData;
  const text = typeof req.body?.text === "string" ? req.body.text.trim() : "";
  const clientTs = typeof req.body?.clientTs === "number" ? req.body.clientTs : null;

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
  // We log only a short prefix + length for local correlation during development.
  // If you truly need full initData for debugging, change this consciously.
  // eslint-disable-next-line no-console
  console.log("[miniapp] /api/command accepted", {
    requestId,
    acceptedId,
    text,
    initDataVerified: ctx.verified,
    initDataPrefix: initData ? initData.slice(0, 48) : "",
    initDataLen: initData.length,
    clientTs,
  });

  // Wire commands into the live state so nodes light up immediately.
  const targetAgent = parseAgent(text) ?? pickNextAgent();
  const activity = inferActivity(text);
  markRealEvent();

  // Visual: ORION is dispatching work outwards.
  addOrionBadge("📤", 2600);

  if (targetAgent === "LEDGER") {
    ledgerPulseIdx += 1;
  }

  if (targetAgent === "LEDGER" && ledgerPulseIdx % 4 === 0) {
    applyEventToStore({ type: "tool.started", agentId: targetAgent });
  } else {
    applyEventToStore({ type: "agent.activity", agentId: targetAgent, activity });
  }

  if (STREAM_CLIENTS.size > 0) {
    sseBroadcast("command.accepted", {
      requestId,
      acceptedId,
      receivedAt: Date.now(),
      targetAgent,
      activity,
      // Avoid pushing initData to clients.
      textPreview: text.slice(0, 120),
    });
    scheduleStateBroadcast();
  }

  // Optional: route the command into ORION via OpenClaw (local-first).
  // Best-effort; deployments without OpenClaw installed can leave this off.
  const shouldRoute = process.env.OPENCLAW_ROUTE_COMMANDS === "1";
  // Prefer DM replies (userId) to avoid spamming groups when a miniapp is opened from a group context.
  const deliverTarget = String(ctx.userId ?? ctx.chatId ?? "").trim();

  // If we're not actually routing into ORION, simulate a quick round-trip so the UI can
  // show a "return transmission" and ORION "receiving" behavior as a control.
  if (!shouldRoute || !deliverTarget) {
    setTimeout(() => {
      applyEventToStore({ type: "task.completed", agentId: targetAgent });
      if (STREAM_CLIENTS.size > 0) {
        sseBroadcast("task.completed", {
          id: acceptedId,
          ts: Date.now(),
          type: "task.completed",
          data: { requestId, ok: true, code: 0, agentId: targetAgent, simulated: true },
        });
        scheduleStateBroadcast();
      }
    }, 1200);
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

    try {
      const child = spawn("openclaw", args, {
        stdio: ["ignore", "pipe", "pipe"],
        env: process.env,
      });

      let out = "";
      let err = "";
      child.stdout.on("data", (d) => {
        out += d.toString("utf8");
      });
      child.stderr.on("data", (d) => {
        err += d.toString("utf8");
      });
      child.on("error", (e) => {
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
        const ok = code === 0;
        const preview = (ok ? out : err).trim().slice(0, 600);
        // eslint-disable-next-line no-console
        console.log("[miniapp] openclaw route result", { ok, code, preview });

        // Treat completion as a return-flow back into ORION.
        applyEventToStore({ type: ok ? "task.completed" : "task.failed", agentId: targetAgent });
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
  app.use(express.static(distDir));
  app.get("*", (req, res) => {
    res.sendFile(distIndex);
  });
}

app.listen(PORT, HOST, () => {
  // eslint-disable-next-line no-console
  console.log(`[miniapp] listening on http://${HOST}:${PORT}`);
});
