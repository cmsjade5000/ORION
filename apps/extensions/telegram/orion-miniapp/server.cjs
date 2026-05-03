const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");

const { createChatManager } = require("./chat.cjs");
const { publicConfig } = require("./config.cjs");
const { validateInitData } = require("./auth.cjs");
const {
  approvalSnapshot,
  findJobById,
  homeState,
  inboxState,
  jobDetail,
  packetPreview,
  persistQueueRequest,
  readQueueRequests,
  recentQueueRequestForJob,
  reviewState,
  runJsonCommand,
  runTextCommand,
  updateQueueRequestStatus,
} = require("./state.cjs");

const CONFIG = publicConfig();
const PUBLIC_DIR = path.join(__dirname, "public");
const chatManager = createChatManager({ workspaceRoot: CONFIG.workspaceRoot });
const activeFollowupJobs = new Set();

function sendJson(res, statusCode, payload) {
  res.writeHead(statusCode, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(payload));
}

function sendText(res, statusCode, payload, contentType = "text/plain; charset=utf-8", extraHeaders = {}) {
  res.writeHead(statusCode, { "Content-Type": contentType, ...extraHeaders });
  res.end(payload);
}

function logRequest(req, pathname) {
  const userAgent = String(req.headers["user-agent"] || "").replace(/\s+/g, " ").slice(0, 240);
  console.log(`[miniapp-request] method=${req.method} path=${pathname} ua=${userAgent}`);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => {
      body += String(chunk);
      if (body.length > 1024 * 1024) {
        reject(new Error("request-body-too-large"));
        req.destroy();
      }
    });
    req.on("end", () => resolve(body));
    req.on("error", reject);
  });
}

function logClientError(req, body) {
  try {
    const payload = JSON.parse(body || "{}");
    const kind = String(payload.kind || "client-error").replace(/[^\w.-]/g, "_").slice(0, 64);
    const detail = String(payload.detail || "").replace(/\s+/g, " ").slice(0, 500);
    const userAgent = String(payload.userAgent || req.headers["user-agent"] || "").replace(/\s+/g, " ").slice(0, 240);
    const href = String(payload.href || "").slice(0, 240);
    console.error(`[miniapp-client-error] kind=${kind} detail=${detail} href=${href} ua=${userAgent}`);
  } catch (error) {
    console.error("[miniapp-client-error] unreadable payload");
  }
}

function publicApiError(error) {
  const message = error instanceof Error ? error.message : String(error || "");
  if (/miniapp-auth:/i.test(message)) return message;
  if (/job not found/i.test(message)) return "job not found";
  if (/job is not blocked/i.test(message)) return message;
  if (/already queuing/i.test(message)) return "follow-up already queuing";
  return "ORION could not complete that backend action.";
}

function actorFromTelegram(fields) {
  const user = fields && fields.user ? fields.user : {};
  const id = user && user.id ? String(user.id) : "unknown";
  const username = user && user.username ? ` @${String(user.username)}` : "";
  const firstName = user && user.first_name ? ` ${String(user.first_name)}` : "";
  return `telegram:${id}${username}${firstName}`.trim();
}

function initDataFromRequest(req) {
  try {
    const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
    const encodedValue = String(url.searchParams.get("initDataB64") || "").trim();
    if (encodedValue) {
      try {
        return Buffer.from(encodedValue, "base64url").toString("utf8").trim();
      } catch {
        // Fall through to the raw query/header paths if decoding fails.
      }
    }
    const queryValue = String(url.searchParams.get("initData") || "").trim();
    if (queryValue) return queryValue;
  } catch {
    // Ignore malformed URL input and fall through to headers.
  }
  const header = String(req.headers["x-telegram-init-data"] || "").trim();
  if (header) return header;
  const auth = String(req.headers.authorization || "").trim();
  if (auth.toLowerCase().startsWith("tma ")) {
    return auth.slice(4).trim();
  }
  return "";
}

function isAllowedOperator(fields) {
  const ids = CONFIG.operatorIds;
  if (!ids.length) return false;
  const userId = String(fields && fields.user && fields.user.id ? fields.user.id : "");
  return ids.includes(userId);
}

async function answerWebAppQuery(queryId, messageText) {
  const token = CONFIG.botToken;
  if (!token) {
    throw new Error("ORION_TELEGRAM_BOT_TOKEN is not configured for approval actions.");
  }
  const response = await fetch(`https://api.telegram.org/bot${token}/answerWebAppQuery`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      web_app_query_id: queryId,
      result: {
        type: "article",
        id: cryptoRandomId(),
        title: "ORION approval",
        input_message_content: {
          message_text: messageText,
        },
      },
    }),
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload.description || "Telegram answerWebAppQuery failed");
  }
  return payload;
}

function cryptoRandomId() {
  return Math.random().toString(16).slice(2) + Date.now().toString(16);
}

function serveStatic(req, res, fileName, contentType) {
  const target = path.join(PUBLIC_DIR, fileName);
  try {
    const payload = fs.readFileSync(target);
    sendText(res, 200, payload, contentType, {
      "Cache-Control": "no-store, no-cache, must-revalidate",
      Pragma: "no-cache",
      Expires: "0",
    });
  } catch {
    sendText(res, 404, "not found");
  }
}

function staticVersion(fileName) {
  try {
    const stat = fs.statSync(path.join(PUBLIC_DIR, fileName));
    return `${Math.round(stat.mtimeMs)}-${stat.size}`;
  } catch {
    return String(Date.now());
  }
}

function serveIndex(req, res) {
  const target = path.join(PUBLIC_DIR, "index.html");
  try {
    const payload = fs
      .readFileSync(target, "utf8")
      .replace(/\/app\.js(["'])/g, `/app.js?v=${staticVersion("app.js")}$1`)
      .replace(/\/styles\.css(["'])/g, `/styles.css?v=${staticVersion("styles.css")}$1`);
    sendText(res, 200, payload, "text/html; charset=utf-8", {
      "Cache-Control": "no-store, no-cache, must-revalidate",
      Pragma: "no-cache",
      Expires: "0",
    });
  } catch {
    sendText(res, 404, "not found");
  }
}

async function withAuth(req, res, handler) {
  const rawInitData = initDataFromRequest(req);
  const validated = validateInitData(rawInitData, CONFIG.botToken, {
    maxAgeSeconds: CONFIG.allowedClockSkewSeconds,
  });
  if (!validated.ok) {
    sendJson(res, 401, { error: `miniapp-auth:${validated.reason}` });
    return;
  }
  if (!isAllowedOperator(validated.fields)) {
    sendJson(res, 403, { error: "miniapp-auth:not-allowlisted" });
    return;
  }
  try {
    await handler(validated.fields);
  } catch (error) {
    sendJson(res, 500, {
      error: publicApiError(error),
    });
  }
}

async function routeApi(req, res, pathname) {
  if (pathname === "/api/bootstrap") {
    return withAuth(req, res, async (fields) => {
      sendJson(res, 200, {
        appName: CONFIG.appName,
        startapp:
          new URL(req.url, `http://${req.headers.host || "localhost"}`).searchParams.get("startapp") ||
          new URL(req.url, `http://${req.headers.host || "localhost"}`).searchParams.get("tgWebAppStartParam") ||
          "home",
        user: fields.user || null,
        hasQueryId: Boolean(fields.query_id),
        operatorIdsConfigured: CONFIG.operatorIds.length > 0,
        conversation: chatManager.bootstrap(fields.user || {}),
      });
    });
  }

  if (pathname === "/api/home") {
    return withAuth(req, res, async () => {
      sendJson(res, 200, await homeState(CONFIG.workspaceRoot));
    });
  }

  if (pathname === "/api/review") {
    return withAuth(req, res, async () => {
      sendJson(res, 200, await reviewState(CONFIG.workspaceRoot));
    });
  }

  if (pathname === "/api/work") {
    return withAuth(req, res, async () => {
      sendJson(res, 200, packetPreview(CONFIG.workspaceRoot));
    });
  }

  if (pathname === "/api/inbox") {
    return withAuth(req, res, async () => {
      sendJson(res, 200, inboxState(CONFIG.workspaceRoot));
    });
  }

  if (pathname === "/api/queue-requests" && req.method === "GET") {
    return withAuth(req, res, async () => {
      sendJson(res, 200, { ok: true, queueRequests: readQueueRequests(CONFIG.workspaceRoot, 20) });
    });
  }

  const jobDetailMatch = pathname.match(/^\/api\/inbox\/jobs\/([^/]+)$/i);
  if (jobDetailMatch && req.method === "GET") {
    return withAuth(req, res, async () => {
      const detail = jobDetail(CONFIG.workspaceRoot, decodeURIComponent(jobDetailMatch[1]));
      if (!detail) {
        sendJson(res, 404, { error: "job not found" });
        return;
      }
      sendJson(res, 200, detail);
    });
  }

  if (pathname === "/api/approvals") {
    return withAuth(req, res, async () => {
      sendJson(res, 200, await approvalSnapshot(CONFIG.workspaceRoot));
    });
  }

  if (pathname === "/api/capture" && req.method === "POST") {
    return withAuth(req, res, async () => {
      const body = JSON.parse((await readBody(req)) || "{}");
      const text = String(body.text || "").trim();
      const notify = String(body.notify || "telegram").trim();
      if (!text) {
        sendJson(res, 400, { error: "capture text is required" });
        return;
      }
      const payload = await runJsonCommand(
        "python3",
        [
          "scripts/assistant_capture.py",
          "--repo-root",
          CONFIG.workspaceRoot,
          "--text",
          text,
          "--notify",
          notify === "none" ? "none" : "telegram",
          "--json",
        ],
        CONFIG.workspaceRoot
      );
      sendJson(res, 200, payload || { message: "Captured." });
    });
  }

  if (pathname === "/api/chat/runs" && req.method === "POST") {
    return withAuth(req, res, async (fields) => {
      const body = JSON.parse((await readBody(req)) || "{}");
      const message = String(body.message || "").trim();
      if (!message) {
        sendJson(res, 400, { error: "chat message is required" });
        return;
      }
      sendJson(res, 200, chatManager.createRun(fields.user || {}, message));
    });
  }

  const runMatch = pathname.match(/^\/api\/chat\/runs\/([^/]+)$/i);
  if (runMatch && req.method === "GET") {
    return withAuth(req, res, async () => {
      const run = chatManager.getRun(runMatch[1]);
      if (!run) {
        sendJson(res, 404, { error: "chat run not found" });
        return;
      }
      sendJson(res, 200, run);
    });
  }

  const streamMatch = pathname.match(/^\/api\/chat\/runs\/([^/]+)\/events$/i);
  if (streamMatch && req.method === "GET") {
    const rawInitData = initDataFromRequest(req);
    const validated = validateInitData(rawInitData, CONFIG.botToken, {
      maxAgeSeconds: CONFIG.allowedClockSkewSeconds,
    });
    if (!validated.ok) {
      sendJson(res, 401, { error: `miniapp-auth:${validated.reason}` });
      return;
    }
    if (!isAllowedOperator(validated.fields)) {
      sendJson(res, 403, { error: "miniapp-auth:not-allowlisted" });
      return;
    }
    const lastEventId = req.headers["last-event-id"] || new URL(req.url, `http://${req.headers.host || "localhost"}`).searchParams.get("lastEventId");
    const ok = chatManager.subscribe(streamMatch[1], res, lastEventId);
    if (!ok) {
      sendJson(res, 404, { error: "chat run not found" });
    }
    return;
  }

  const approvalMatch = pathname.match(/^\/api\/approvals\/([0-9a-f-]+)\/action$/i);
  if (approvalMatch && req.method === "POST") {
    return withAuth(req, res, async (fields) => {
      const body = JSON.parse((await readBody(req)) || "{}");
      const decision = String(body.decision || "").trim().toLowerCase();
      const approvalId = approvalMatch[1];
      if (!["allow-once", "allow-always", "deny"].includes(decision)) {
        sendJson(res, 400, { error: "unsupported approval decision" });
        return;
      }
      const command = `/approve ${approvalId} ${decision}`;
      const queryId = String(fields.query_id || "").trim();
      if (queryId) {
        try {
          await answerWebAppQuery(queryId, command);
          sendJson(res, 200, {
            ok: true,
            closesWebApp: true,
            message: `Approval command sent as you: ${command}`,
          });
          return;
        } catch (error) {
          console.error(`[miniapp-approvals] answerWebAppQuery failed: ${error instanceof Error ? error.message : String(error)}`);
        }
      }
      sendJson(res, 200, {
        ok: true,
        closesWebApp: false,
        message: `No live query context was available. Run this manually in Telegram: ${command}`,
        manualCommand: command,
      });
    });
  }

  const followupMatch = pathname.match(/^\/api\/jobs\/([^/]+)\/followup$/i);
  if (followupMatch && req.method === "POST") {
    return withAuth(req, res, async () => {
      const jobId = decodeURIComponent(followupMatch[1]);
      const job = findJobById(CONFIG.workspaceRoot, jobId);
      if (!job) {
        sendJson(res, 404, { error: "job not found" });
        return;
      }
      const lockKey = String(job.job_id || jobId);
      if (activeFollowupJobs.has(lockKey)) {
        sendJson(res, 409, { error: "follow-up already queuing" });
        return;
      }
      const recentRequest = recentQueueRequestForJob(CONFIG.workspaceRoot, job.job_id);
      if (recentRequest) {
        sendJson(res, 200, {
          ok: true,
          duplicate: true,
          message: recentRequest.message,
          request: recentRequest,
        });
        return;
      }
      activeFollowupJobs.add(lockKey);
      try {
        const inboxPath = job.inbox && job.inbox.path ? `${job.inbox.path}${job.inbox.line ? `:${job.inbox.line}` : ""}` : "n/a";
        const captureText = [
          "Follow up on delegated ORION work.",
          `Owner: ${job.owner || "unknown"}`,
          `State: ${job.state || "unknown"}`,
          `Objective: ${job.objective || "(no objective)"}`,
          `Inbox: ${inboxPath}`,
        ].join("\n");
        const payload = await runJsonCommand(
          "python3",
          [
            "scripts/assistant_capture.py",
            "--repo-root",
            CONFIG.workspaceRoot,
            "--text",
            captureText,
            "--notify",
            "telegram",
            "--json",
          ],
          CONFIG.workspaceRoot
        );
        const request = persistQueueRequest(CONFIG.workspaceRoot, {
          jobId: job.job_id,
          owner: "POLARIS",
          status: "queued",
          message: payload && payload.message ? payload.message : "Follow-up queued for POLARIS.",
          intakePath: payload && payload.intake_path ? payload.intake_path : "",
          packetNumber: payload && payload.packet_number ? payload.packet_number : undefined,
        });
        sendJson(res, 200, {
          ok: true,
          message: request.message,
          request,
        });
      } finally {
        activeFollowupJobs.delete(lockKey);
      }
    });
  }

  const taskApprovalMatch = pathname.match(/^\/api\/jobs\/([^/]+)\/task-approval$/i);
  if (taskApprovalMatch && req.method === "POST") {
    return withAuth(req, res, async (fields) => {
      const body = JSON.parse((await readBody(req)) || "{}");
      const rawDecision = String(body.decision || "").trim().toLowerCase();
      const decision = rawDecision === "approve-once" ? "approve_once" : rawDecision;
      if (!["approve_once", "deny"].includes(decision)) {
        sendJson(res, 400, { error: "unsupported task packet approval decision" });
        return;
      }
      const payload = await runJsonCommand(
        "python3",
        [
          "scripts/task_packet_approvals.py",
          "--repo-root",
          CONFIG.workspaceRoot,
          "--json",
          "decide",
          "--job-id",
          decodeURIComponent(taskApprovalMatch[1]),
          "--decision",
          decision,
          "--actor",
          actorFromTelegram(fields),
        ],
        CONFIG.workspaceRoot
      );
      if (!payload || payload.ok === false) {
        sendJson(res, 500, { error: payload && payload.error ? payload.error : "task packet approval failed" });
        return;
      }
      try {
        payload.reconcile = await runTextCommand(
          "python3",
          ["scripts/task_execution_loop.py", "--repo-root", CONFIG.workspaceRoot, "--apply", "--stale-hours", "24"],
          CONFIG.workspaceRoot
        );
      } catch (error) {
        payload.reconcileError = error instanceof Error ? error.message : String(error || "reconcile failed");
      }
      sendJson(res, 200, payload);
    });
  }

  const queueStatusMatch = pathname.match(/^\/api\/queue-requests\/([^/]+)\/status$/i);
  if (queueStatusMatch && req.method === "PATCH") {
    return withAuth(req, res, async () => {
      const body = JSON.parse((await readBody(req)) || "{}");
      const status = String(body.status || "").trim();
      const request = updateQueueRequestStatus(CONFIG.workspaceRoot, decodeURIComponent(queueStatusMatch[1]), status);
      if (!request) {
        sendJson(res, 404, { error: "queue request not found" });
        return;
      }
      sendJson(res, 200, { ok: true, request });
    });
  }

  sendJson(res, 404, { error: "not found" });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
  const pathname = url.pathname;

  if (pathname === "/healthz" || pathname === "/readyz") {
    sendJson(res, 200, { ok: true, app: CONFIG.appName });
    return;
  }
  if (pathname === "/app.js") {
    logRequest(req, pathname);
    serveStatic(req, res, "app.js", "application/javascript; charset=utf-8");
    return;
  }
  if (pathname === "/styles.css") {
    logRequest(req, pathname);
    serveStatic(req, res, "styles.css", "text/css; charset=utf-8");
    return;
  }
  if (pathname === "/client-error" && req.method === "POST") {
    logRequest(req, pathname);
    try {
      logClientError(req, await readBody(req));
    } catch {
      console.error("[miniapp-client-error] failed to read payload");
    }
    sendJson(res, 200, { ok: true });
    return;
  }
  if (pathname.startsWith("/api/")) {
    await routeApi(req, res, pathname);
    return;
  }
  logRequest(req, pathname);
  serveIndex(req, res);
});

if (require.main === module) {
  server.listen(CONFIG.port, CONFIG.host, () => {
    console.log(`ORION mini app listening on http://${CONFIG.host}:${CONFIG.port}`);
  });
}

module.exports = {
  server,
};
