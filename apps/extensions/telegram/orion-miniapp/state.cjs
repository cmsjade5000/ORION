const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
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

function isCompletedJob(job) {
  const state = String(job && job.state ? job.state : "").toLowerCase();
  const result = job && typeof job.result === "object" && job.result ? job.result : {};
  const resultStatus = String(result.status || "").toLowerCase();
  return state === "complete" || resultStatus === "ok";
}

function packetPreview(workspaceRoot) {
  const summary = jobsSummary(workspaceRoot);
  const jobs = Array.isArray(summary.jobs) ? summary.jobs : [];
  return {
    counts: summary.counts || {},
    updatedTs: summary.updated_ts || null,
    jobs: jobs.filter((job) => !isCompletedJob(job)).slice(0, 8),
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
  };
}

function findJobById(workspaceRoot, jobId) {
  const summary = jobsSummary(workspaceRoot);
  const jobs = Array.isArray(summary.jobs) ? summary.jobs : [];
  return jobs.find((job) => String(job.job_id || "") === String(jobId || "")) || null;
}

module.exports = {
  approvalSnapshot,
  assistantMessage,
  extractApprovalFromText,
  findJobById,
  homeState,
  inboxState,
  isCompletedJob,
  jobsSummary,
  packetPreview,
  readJson,
  readJsonLines,
  recentApprovalPrompts,
  reviewState,
  runJsonCommand,
  runTextCommand,
};
