const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const crypto = require("node:crypto");
const { execFile } = require("node:child_process");
const { promisify } = require("node:util");

const execFileAsync = promisify(execFile);

function repoRootFromWorkspace(workspaceRoot) {
  return path.resolve(workspaceRoot || process.cwd());
}

function readJson(filePath, fallback = null) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return fallback;
  }
}

function readJsonLines(filePath) {
  try {
    return fs
      .readFileSync(filePath, "utf8")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line));
  } catch {
    return [];
  }
}

function queueRequestsPath(workspaceRoot) {
  const repoRoot = repoRootFromWorkspace(workspaceRoot);
  return path.join(repoRoot, "tasks", "STATE", "miniapp_queue_requests.json");
}

function normalizeQueueRequest(row) {
  if (!row || typeof row !== "object") return null;
  const status = String(row.status || "").trim();
  if (!["queued", "refresh_delayed", "failed"].includes(status)) return null;
  const id = String(row.id || "").trim();
  const jobId = String(row.jobId || row.job_id || "").trim();
  const createdAt = String(row.createdAt || "").trim();
  if (!id || !jobId || !createdAt) return null;
  const packetNumber = Number(row.packetNumber || row.packet_number || 0);
  return {
    id,
    jobId,
    owner: "POLARIS",
    status,
    message: String(row.message || "").trim() || "Follow-up queued for POLARIS.",
    intakePath: String(row.intakePath || row.intake_path || "").trim(),
    ...(Number.isFinite(packetNumber) && packetNumber > 0 ? { packetNumber } : {}),
    createdAt,
  };
}

function readQueueRequests(workspaceRoot, limit = 20) {
  const filePath = queueRequestsPath(workspaceRoot);
  const payload = readJson(filePath, { requests: [] });
  const rows = Array.isArray(payload) ? payload : Array.isArray(payload.requests) ? payload.requests : [];
  return rows
    .map(normalizeQueueRequest)
    .filter(Boolean)
    .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt))
    .slice(0, limit);
}

function writeQueueRequests(workspaceRoot, requests) {
  const filePath = queueRequestsPath(workspaceRoot);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const normalized = (Array.isArray(requests) ? requests : [])
    .map(normalizeQueueRequest)
    .filter(Boolean)
    .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt))
    .slice(0, 40);
  const payload = {
    version: 1,
    updatedAt: new Date().toISOString(),
    requests: normalized,
  };
  const tempPath = `${filePath}.${process.pid}.tmp`;
  fs.writeFileSync(tempPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  fs.renameSync(tempPath, filePath);
  return normalized;
}

function recentQueueRequestForJob(workspaceRoot, jobId, maxAgeMinutes = 10) {
  const targetJobId = String(jobId || "").trim();
  if (!targetJobId) return null;
  const maxAgeMs = maxAgeMinutes * 60 * 1000;
  const now = Date.now();
  return (
    readQueueRequests(workspaceRoot, 40).find((request) => {
      const ageMs = now - Date.parse(request.createdAt);
      return request.jobId === targetJobId && request.status !== "failed" && Number.isFinite(ageMs) && ageMs >= 0 && ageMs <= maxAgeMs;
    }) || null
  );
}

function persistQueueRequest(workspaceRoot, input) {
  const request = normalizeQueueRequest({
    id: input.id || `qr_${Date.now().toString(36)}_${crypto.randomBytes(4).toString("hex")}`,
    jobId: input.jobId,
    owner: "POLARIS",
    status: input.status || "queued",
    message: input.message,
    intakePath: input.intakePath,
    packetNumber: input.packetNumber,
    createdAt: input.createdAt || new Date().toISOString(),
  });
  if (!request) {
    throw new Error("invalid queue request");
  }
  const existing = readQueueRequests(workspaceRoot, 40).filter((row) => row.id !== request.id);
  writeQueueRequests(workspaceRoot, [request, ...existing]);
  return request;
}

function updateQueueRequestStatus(workspaceRoot, requestId, status) {
  const targetId = String(requestId || "").trim();
  const nextStatus = String(status || "").trim();
  if (!targetId || !["queued", "refresh_delayed", "failed"].includes(nextStatus)) return null;
  let updated = null;
  const requests = readQueueRequests(workspaceRoot, 40).map((request) => {
    if (request.id !== targetId) return request;
    updated = { ...request, status: nextStatus };
    return updated;
  });
  if (!updated) return null;
  writeQueueRequests(workspaceRoot, requests);
  return updated;
}

async function runJsonCommand(command, argv, cwd, env = process.env) {
  const { stdout, stderr } = await execFileAsync(command, argv, {
    cwd,
    env,
    maxBuffer: 8 * 1024 * 1024,
  });
  const out = String(stdout || stderr || "").trim();
  return out ? JSON.parse(out) : null;
}

async function runTextCommand(command, argv, cwd, env = process.env) {
  const { stdout, stderr } = await execFileAsync(command, argv, {
    cwd,
    env,
    maxBuffer: 8 * 1024 * 1024,
  });
  return String(stdout || stderr || "").trim();
}

async function assistantMessage(workspaceRoot, command) {
  const repoRoot = repoRootFromWorkspace(workspaceRoot);
  const payload = await runJsonCommand(
    "python3",
    ["scripts/assistant_status.py", "--repo-root", repoRoot, "--cmd", command, "--json"],
    repoRoot
  );
  return String(payload && payload.message ? payload.message : "").trim();
}

function jobsSummary(workspaceRoot) {
  const repoRoot = repoRootFromWorkspace(workspaceRoot);
  return readJson(path.join(repoRoot, "tasks", "JOBS", "summary.json"), {
    counts: {},
    jobs: [],
    workflows: [],
  });
}

function packetPreview(workspaceRoot) {
  const summary = jobsSummary(workspaceRoot);
  return {
    counts: summary.counts || {},
    updatedTs: summary.updated_ts || null,
    jobs: Array.isArray(summary.jobs) ? summary.jobs.slice(0, 8) : [],
    workflows: Array.isArray(summary.workflows) ? summary.workflows.slice(0, 6) : [],
  };
}

function approvalRegexes() {
  return [
    /\/approve\s+([0-9a-f-]+)\s+(allow-once|allow-always|deny)/i,
    /\/deny\s+([0-9a-f-]+)/i,
  ];
}

function extractApprovalFromText(text) {
  const raw = String(text || "");
  for (const regex of approvalRegexes()) {
    const match = raw.match(regex);
    if (!match) continue;
    if (regex.source.startsWith("\\/deny")) {
      return { approvalId: match[1], suggestedDecision: "deny" };
    }
    return { approvalId: match[1], suggestedDecision: match[2] };
  }
  return null;
}

function approvalRunsDir() {
  return path.join(os.homedir(), ".openclaw", "cron", "runs");
}

function recentApprovalPrompts(maxAgeMinutes = 45) {
  const root = approvalRunsDir();
  const nowMs = Date.now();
  const maxAgeMs = maxAgeMinutes * 60 * 1000;
  const files = (() => {
    try {
      return fs
        .readdirSync(root)
        .filter((name) => name.endsWith(".jsonl"))
        .map((name) => path.join(root, name))
        .map((filePath) => ({ filePath, stat: fs.statSync(filePath) }))
        .sort((a, b) => b.stat.mtimeMs - a.stat.mtimeMs)
        .slice(0, 24)
        .map((entry) => entry.filePath);
    } catch {
      return [];
    }
  })();

  const byId = new Map();
  for (const filePath of files) {
    for (const row of readJsonLines(filePath)) {
      const summary = row && row.summary ? row.summary : "";
      const extracted = extractApprovalFromText(summary);
      if (!extracted) continue;
      const ts = Number(row.ts || 0);
      if (!Number.isFinite(ts) || ts <= 0) continue;
      const ageMs = nowMs - ts;
      if (ageMs > maxAgeMs) continue;
      const current = byId.get(extracted.approvalId);
      if (current && current.ts >= ts) continue;
      byId.set(extracted.approvalId, {
        approvalId: extracted.approvalId,
        suggestedDecision: extracted.suggestedDecision,
        summary: String(summary || "").trim(),
        label: String(row.jobId || row.sessionKey || "approval"),
        sessionId: String(row.sessionId || ""),
        sessionKey: String(row.sessionKey || ""),
        ts,
        ageMs,
      });
    }
  }
  return [...byId.values()].sort((a, b) => b.ts - a.ts);
}

async function approvalSnapshot(workspaceRoot) {
  const repoRoot = repoRootFromWorkspace(workspaceRoot);
  let snapshot = null;
  let error = "";
  try {
    snapshot = await runJsonCommand("openclaw", ["approvals", "get", "--json"], repoRoot);
  } catch (err) {
    error = err instanceof Error ? err.message : String(err || "unknown error");
  }
  return {
    backend: "openclaw-exec-approvals",
    snapshot,
    error,
    pending: recentApprovalPrompts(),
  };
}

async function homeState(workspaceRoot) {
  const [today, review, approvals] = await Promise.all([
    assistantMessage(workspaceRoot, "today"),
    assistantMessage(workspaceRoot, "review"),
    approvalSnapshot(workspaceRoot),
  ]);
  const packets = packetPreview(workspaceRoot);
  return {
    today,
    review,
    approvalsCount: approvals.pending.length,
    pendingApprovals: approvals.pending.slice(0, 3),
    jobCounts: packets.counts,
    jobs: packets.jobs.slice(0, 4),
    updatedTs: packets.updatedTs,
  };
}

async function reviewState(workspaceRoot) {
  const [today, followups, review] = await Promise.all([
    assistantMessage(workspaceRoot, "today"),
    assistantMessage(workspaceRoot, "followups"),
    assistantMessage(workspaceRoot, "review"),
  ]);
  return { today, followups, review };
}

function inboxState(workspaceRoot) {
  const packets = packetPreview(workspaceRoot);
  const approvals = recentApprovalPrompts();
  const jobs = Array.isArray(packets.jobs) ? packets.jobs : [];
  const blockedJobs = jobs.filter((job) => String(job.state || "").toLowerCase() === "blocked");
  const pendingVerificationJobs = jobs.filter(
    (job) => String(job.state || "").toLowerCase() === "pending_verification"
  );
  return {
    counts: packets.counts,
    updatedTs: packets.updatedTs,
    approvals,
    jobs,
    blockedJobs,
    pendingVerificationJobs,
    queueRequests: readQueueRequests(workspaceRoot, 20),
  };
}

function findJobById(workspaceRoot, jobId) {
  const jobs = packetPreview(workspaceRoot).jobs || [];
  return jobs.find((job) => String(job.job_id || "") === String(jobId || "")) || null;
}

module.exports = {
  approvalSnapshot,
  assistantMessage,
  extractApprovalFromText,
  findJobById,
  homeState,
  inboxState,
  jobsSummary,
  packetPreview,
  persistQueueRequest,
  queueRequestsPath,
  readJson,
  readJsonLines,
  readQueueRequests,
  recentApprovalPrompts,
  recentQueueRequestForJob,
  reviewState,
  runJsonCommand,
  runTextCommand,
  updateQueueRequestStatus,
};
