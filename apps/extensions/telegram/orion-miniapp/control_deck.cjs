const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const crypto = require("node:crypto");
const { runTextCommand } = require("./state.cjs");

const SNAPSHOT_LANES = ["overview", "orion", "workstation", "repos", "cleanup", "activity"];
const SEVERITY_RANK = { ok: 0, info: 1, warning: 2, critical: 3 };
const ACTIONS = [
  {
    id: "refresh-snapshot",
    label: "Refresh Snapshot",
    previewable: true,
    mutates: false,
  },
  {
    id: "acknowledge-issue",
    label: "Acknowledge Issue",
    previewable: true,
    mutates: false,
  },
  {
    id: "preview-cleanup",
    label: "Preview Cleanup",
    previewable: true,
    mutates: false,
  },
  {
    id: "quarantine-cleanup",
    label: "Quarantine Cleanup",
    previewable: true,
    mutates: true,
    requiresConfirmation: "QUARANTINE",
  },
  {
    id: "restore-quarantine",
    label: "Restore Quarantine",
    previewable: true,
    mutates: true,
    requiresConfirmation: "RESTORE",
  },
];

function repoRootFromWorkspace(workspaceRoot) {
  return path.resolve(workspaceRoot || process.cwd());
}

function nowFromOptions(options) {
  return typeof options.now === "function" ? options.now() : new Date();
}

function controlDeckStateDir(workspaceRoot) {
  return path.join(repoRootFromWorkspace(workspaceRoot), "tmp", "control-deck");
}

function quarantineRoot(workspaceRoot) {
  return path.join(repoRootFromWorkspace(workspaceRoot), "tmp", "control-deck-quarantine");
}

function auditPath(workspaceRoot) {
  return path.join(controlDeckStateDir(workspaceRoot), "audit.jsonl");
}

function tokenPath(workspaceRoot) {
  return path.join(controlDeckStateDir(workspaceRoot), "loopback-token");
}

function manifestPath(workspaceRoot) {
  return path.join(quarantineRoot(workspaceRoot), "manifest.json");
}

function readJson(filePath, fallback) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return fallback;
  }
}

function writeJsonAtomic(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const tmpPath = `${filePath}.${process.pid}.${Date.now()}.tmp`;
  fs.writeFileSync(tmpPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  fs.renameSync(tmpPath, filePath);
}

function appendJsonLine(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.appendFileSync(filePath, `${JSON.stringify(payload)}\n`, "utf8");
}

function readControlDeckAudit(workspaceRoot, limit = 80) {
  try {
    return fs
      .readFileSync(auditPath(workspaceRoot), "utf8")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line))
      .reverse()
      .slice(0, limit);
  } catch {
    return [];
  }
}

function writeAudit(workspaceRoot, entry) {
  const createdAt = new Date().toISOString();
  appendJsonLine(auditPath(workspaceRoot), {
    createdAt,
    source: "control-deck",
    ...entry,
  });
}

function hashId(value, prefix = "cd") {
  return `${prefix}_${crypto.createHash("sha256").update(String(value)).digest("hex").slice(0, 16)}`;
}

function safeDetail(value, maxLength = 420) {
  return String(value || "")
    .replace(/(api[_-]?key|token|secret|password)\s*[:=]\s*['"]?[^'"\s]+/gi, "$1=[redacted]")
    .replace(/[A-Za-z0-9_=-]{32,}/g, "[redacted]")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, maxLength);
}

function evidence(label, detail, source = "local") {
  return {
    label: String(label || "evidence"),
    detail: safeDetail(detail || "unavailable"),
    source,
  };
}

function signal({ id, lane, title, status = "ok", severity = "ok", verdict, evidence: entries = [], recommendedAction = "" }) {
  return {
    id,
    lane,
    title,
    status,
    severity,
    verdict: verdict || (status === "ok" ? "Healthy" : "Needs attention"),
    evidence: entries,
    freshness: { generatedAt: new Date().toISOString(), source: "local" },
    recommendedAction,
  };
}

async function runCommand(command, argv, cwd, options = {}) {
  try {
    if (typeof options.commandRunner === "function") {
      const result = await options.commandRunner(command, argv, cwd);
      if (result && typeof result === "object" && "stdout" in result) {
        return { ok: true, stdout: safeDetail(result.stdout, 16 * 1024), error: "" };
      }
      return { ok: true, stdout: safeDetail(result, 16 * 1024), error: "" };
    }
    const stdout = await runTextCommand(command, argv, cwd, process.env, 8000, 512 * 1024);
    return { ok: true, stdout: safeDetail(stdout, 16 * 1024), error: "" };
  } catch (error) {
    return {
      ok: false,
      stdout: "",
      error: safeDetail(error instanceof Error ? error.message : String(error || "failed")),
    };
  }
}

function statfsSignal(targetPath, title, generatedAt) {
  try {
    const stats = fs.statfsSync(targetPath);
    const totalBytes = Number(stats.blocks || 0) * Number(stats.bsize || 0);
    const freeBytes = Number(stats.bavail || 0) * Number(stats.bsize || 0);
    const freePercent = totalBytes > 0 ? Math.round((freeBytes / totalBytes) * 1000) / 10 : null;
    const severity = freePercent !== null && freePercent < 8 ? "critical" : freePercent !== null && freePercent < 15 ? "warning" : "ok";
    return {
      id: hashId(`disk:${targetPath}`),
      lane: "workstation",
      title,
      status: "ok",
      severity,
      verdict: freePercent === null ? "Disk size unavailable" : `${freePercent}% free`,
      evidence: [evidence(targetPath, `${Math.round(freeBytes / 1024 / 1024 / 1024)} GB free`)],
      freshness: { generatedAt, source: "statfs" },
      recommendedAction: severity === "ok" ? "Keep monitoring." : "Review cleanup candidates before quarantining anything.",
    };
  } catch (error) {
    return {
      id: hashId(`disk:${targetPath}`),
      lane: "workstation",
      title,
      status: "degraded",
      severity: "warning",
      verdict: "Disk signal unavailable",
      evidence: [evidence(targetPath, error instanceof Error ? error.message : "unavailable")],
      freshness: { generatedAt, source: "statfs" },
      recommendedAction: "Try again locally; do not infer disk health from this missing signal.",
    };
  }
}

function collectDiskSignals(generatedAt) {
  const targets = [
    ["/System/Volumes/Data", "Data Volume"],
    [os.homedir(), "Home Directory"],
  ];
  return targets.map(([targetPath, title]) => statfsSignal(targetPath, title, generatedAt));
}

function collectLaunchAgentSignals(generatedAt) {
  const dirs = [path.join(os.homedir(), "Library", "LaunchAgents"), "/Library/LaunchAgents"];
  const matches = [];
  for (const dir of dirs) {
    let names = [];
    try {
      names = fs.readdirSync(dir);
    } catch {
      continue;
    }
    for (const name of names) {
      if (!/(orion|openclaw|codex|storage|remodex)/i.test(name)) continue;
      const filePath = path.join(dir, name);
      let mtime = "";
      try {
        mtime = fs.statSync(filePath).mtime.toISOString();
      } catch {
        mtime = "";
      }
      matches.push({ name, path: filePath, mtime });
    }
  }
  return {
    id: "launchagents",
    lane: "workstation",
    title: "LaunchAgents",
    status: matches.length ? "ok" : "degraded",
    severity: matches.length ? "info" : "warning",
    verdict: matches.length ? `${matches.length} relevant agent${matches.length === 1 ? "" : "s"} found` : "No matching LaunchAgents found",
    evidence: matches.length
      ? matches.slice(0, 12).map((item) => evidence(item.name, `${item.path}${item.mtime ? ` mtime=${item.mtime}` : ""}`))
      : [evidence("launchagents", "No ORION/OpenClaw/Codex/storage/remodex LaunchAgents were visible.")],
    freshness: { generatedAt, source: "filesystem" },
    recommendedAction: matches.length ? "Verify only if an agent looks stale." : "Check live launchctl state before changing anything.",
  };
}

async function collectProcessSignal(workspaceRoot, generatedAt, options) {
  const result = await runCommand("ps", ["axo", "pid,comm,args"], repoRootFromWorkspace(workspaceRoot), options);
  if (!result.ok) {
    return {
      id: "process-highlights",
      lane: "workstation",
      title: "Process Highlights",
      status: "degraded",
      severity: "warning",
      verdict: "Process list unavailable",
      evidence: [evidence("ps", result.error || "unavailable")],
      freshness: { generatedAt, source: "ps" },
      recommendedAction: "Retry locally before restarting services.",
    };
  }
  const lines = result.stdout
    .split("\n")
    .filter((line) => /(orion|openclaw|codex|remodex|node.*orion-miniapp)/i.test(line))
    .slice(0, 16);
  return {
    id: "process-highlights",
    lane: "workstation",
    title: "Process Highlights",
    status: lines.length ? "ok" : "degraded",
    severity: lines.length ? "info" : "warning",
    verdict: lines.length ? `${lines.length} matching process highlight${lines.length === 1 ? "" : "s"}` : "No process highlights found",
    evidence: lines.length ? lines.map((line, index) => evidence(`process-${index + 1}`, line, "ps")) : [evidence("ps", "No matching process rows.")],
    freshness: { generatedAt, source: "ps" },
    recommendedAction: lines.length ? "No action unless a process is stale." : "Confirm gateway status before starting anything.",
  };
}

async function collectToolVersionSignals(workspaceRoot, generatedAt, options) {
  const tools = [
    ["codex", ["--version"]],
    ["openclaw", ["--version"]],
    ["remodex", ["--version"]],
    ["brew", ["--version"]],
  ];
  const entries = [];
  for (const [command, argv] of tools) {
    const result = await runCommand(command, argv, repoRootFromWorkspace(workspaceRoot), options);
    entries.push({
      command,
      ok: result.ok,
      detail: result.ok ? result.stdout.split("\n")[0] || "installed" : result.error || "unavailable",
    });
  }
  const missing = entries.filter((entry) => !entry.ok);
  return {
    id: "tool-versions",
    lane: "workstation",
    title: "Tool Versions",
    status: missing.length ? "degraded" : "ok",
    severity: missing.length ? "warning" : "info",
    verdict: missing.length ? `${missing.length} tool version check${missing.length === 1 ? "" : "s"} unavailable` : "Tool versions visible",
    evidence: entries.map((entry) => evidence(entry.command, entry.detail, "version-check")),
    freshness: { generatedAt, source: "version-check" },
    recommendedAction: missing.length ? "Treat missing version output as unknown, not broken." : "No action.",
  };
}

async function collectBackupSignal(workspaceRoot, generatedAt, options) {
  const result = await runCommand("tmutil", ["latestbackup"], repoRootFromWorkspace(workspaceRoot), options);
  return {
    id: "backup-freshness",
    lane: "workstation",
    title: "Backup Freshness",
    status: result.ok && result.stdout ? "ok" : "degraded",
    severity: result.ok && result.stdout ? "info" : "warning",
    verdict: result.ok && result.stdout ? "Latest Time Machine backup visible" : "Backup freshness unavailable",
    evidence: [evidence("tmutil latestbackup", result.ok ? result.stdout : result.error || "unavailable", "tmutil")],
    freshness: { generatedAt, source: "tmutil" },
    recommendedAction: result.ok ? "No action." : "Check Time Machine manually before relying on restore safety.",
  };
}

async function collectOrionStatusSignal(workspaceRoot, generatedAt, options) {
  const repoRoot = repoRootFromWorkspace(workspaceRoot);
  const result = await runCommand(
    "python3",
    ["scripts/assistant_status.py", "--repo-root", repoRoot, "--cmd", "status", "--json"],
    repoRoot,
    options
  );
  if (!result.ok) {
    return {
      id: "orion-status",
      lane: "orion",
      title: "ORION Status",
      status: "degraded",
      severity: "warning",
      verdict: "assistant_status.py unavailable",
      evidence: [evidence("assistant_status.py", result.error || "unavailable")],
      freshness: { generatedAt, source: "assistant_status.py" },
      recommendedAction: "Inspect status locally before touching queues or services.",
    };
  }
  const parsed = (() => {
    try {
      return JSON.parse(result.stdout);
    } catch {
      return null;
    }
  })();
  const message = parsed && parsed.message ? parsed.message : result.stdout;
  return {
    id: "orion-status",
    lane: "orion",
    title: "ORION Status",
    status: parsed ? "ok" : "degraded",
    severity: parsed ? "info" : "warning",
    verdict: parsed ? "Status command returned JSON" : "Status command returned unreadable output",
    evidence: [evidence("status", message, "assistant_status.py")],
    freshness: { generatedAt, source: "assistant_status.py" },
    recommendedAction: parsed ? "Review anomalies only." : "Run the status command directly for detail.",
  };
}

async function collectRepoSignal(workspaceRoot, generatedAt, options) {
  const srcRoot = path.resolve(repoRootFromWorkspace(workspaceRoot), "..");
  let repos = [];
  try {
    repos = fs
      .readdirSync(srcRoot, { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => path.join(srcRoot, entry.name))
      .filter((dir) => fs.existsSync(path.join(dir, ".git")))
      .slice(0, 16);
  } catch {
    repos = [];
  }
  const entries = [];
  for (const repo of repos) {
    const result = await runCommand("git", ["status", "--short"], repo, options);
    entries.push({
      repo: path.basename(repo),
      ok: result.ok,
      dirtyLines: result.ok && result.stdout ? result.stdout.split("\n").filter(Boolean).length : 0,
      detail: result.ok ? (result.stdout ? `${result.stdout.split("\n").filter(Boolean).length} changed paths` : "clean") : result.error,
    });
  }
  const dirty = entries.filter((entry) => entry.dirtyLines > 0);
  const failed = entries.filter((entry) => !entry.ok);
  return {
    id: "repo-status",
    lane: "repos",
    title: "Repository Status",
    status: failed.length ? "degraded" : "ok",
    severity: failed.length ? "warning" : dirty.length ? "info" : "ok",
    verdict: `${entries.length} repo${entries.length === 1 ? "" : "s"} checked, ${dirty.length} dirty`,
    evidence: entries.length
      ? entries.map((entry) => evidence(entry.repo, entry.detail, "git status"))
      : [evidence("repos", "No git repositories discovered under src.")],
    freshness: { generatedAt, source: "git status" },
    recommendedAction: dirty.length ? "Coordinate with active workers before staging or cleaning." : "No action.",
  };
}

function sizeOfPath(filePath) {
  try {
    const stat = fs.statSync(filePath);
    if (stat.isFile()) return stat.size;
    if (!stat.isDirectory()) return 0;
    return fs
      .readdirSync(filePath)
      .slice(0, 500)
      .reduce((total, name) => total + sizeOfPath(path.join(filePath, name)), 0);
  } catch {
    return 0;
  }
}

function cleanupRoots(workspaceRoot) {
  const repoRoot = repoRootFromWorkspace(workspaceRoot);
  return [
    path.join(repoRoot, "tmp", "control-deck-candidates"),
    path.join(repoRoot, ".pytest_cache"),
    path.join(repoRoot, ".vite"),
    path.join(repoRoot, "tmp"),
  ];
}

function isUnder(parent, child) {
  const relative = path.relative(parent, child);
  return Boolean(relative && !relative.startsWith("..") && !path.isAbsolute(relative));
}

function listCleanupCandidates(workspaceRoot, options = {}) {
  const repoRoot = repoRootFromWorkspace(workspaceRoot);
  const roots = cleanupRoots(repoRoot);
  const nowMs = Number(options.nowMs || Date.now());
  const seen = new Set();
  const candidates = [];
  const maxCandidates = Number(options.maxCandidates || 24);
  const excludedNames = new Set(["control-deck", "control-deck-quarantine", "control-deck-candidates"]);

  for (const root of roots) {
    let entries = [];
    try {
      const stat = fs.statSync(root);
      if (stat.isDirectory()) {
        entries = fs.readdirSync(root).map((name) => path.join(root, name));
      } else {
        entries = [root];
      }
    } catch {
      continue;
    }
    for (const entryPath of entries) {
      const resolved = path.resolve(entryPath);
      const base = path.basename(resolved);
      if (excludedNames.has(base)) continue;
      if (!isUnder(repoRoot, resolved)) continue;
      if (seen.has(resolved)) continue;
      seen.add(resolved);
      let stat;
      try {
        stat = fs.statSync(resolved);
      } catch {
        continue;
      }
      if (!stat.isFile() && !stat.isDirectory()) continue;
      const ageHours = Math.max(0, Math.round(((nowMs - stat.mtimeMs) / 3_600_000) * 10) / 10);
      const bytes = sizeOfPath(resolved);
      candidates.push({
        id: hashId(resolved, "cleanup"),
        path: resolved,
        relativePath: path.relative(repoRoot, resolved),
        type: stat.isDirectory() ? "directory" : "file",
        bytes,
        mtime: stat.mtime.toISOString(),
        ageHours,
        reason: "repo-local generated cleanup candidate",
        observeOnly: false,
      });
    }
  }
  return candidates.sort((a, b) => b.bytes - a.bytes || a.relativePath.localeCompare(b.relativePath)).slice(0, maxCandidates);
}

function collectCleanupSignal(workspaceRoot, generatedAt) {
  const candidates = listCleanupCandidates(workspaceRoot);
  return {
    id: "cleanup-candidates",
    lane: "cleanup",
    title: "Cleanup Candidates",
    status: "ok",
    severity: candidates.length ? "info" : "ok",
    verdict: candidates.length ? `${candidates.length} quarantine-eligible repo-local candidate${candidates.length === 1 ? "" : "s"}` : "No cleanup candidates found",
    evidence: candidates.length
      ? candidates.slice(0, 10).map((candidate) => evidence(candidate.id, `${candidate.relativePath} ${candidate.bytes} bytes`, "cleanup-scan"))
      : [evidence("cleanup", "No repo-local generated candidates found.")],
    freshness: { generatedAt, source: "cleanup-scan" },
    recommendedAction: candidates.length ? "Preview first; quarantine only with explicit confirmation." : "No action.",
    candidates,
  };
}

function collectActivitySignal(workspaceRoot, generatedAt) {
  const audit = readControlDeckAudit(workspaceRoot, 8);
  return {
    id: "control-deck-audit",
    lane: "activity",
    title: "Control Deck Audit",
    status: "ok",
    severity: audit.length ? "info" : "ok",
    verdict: audit.length ? `${audit.length} recent audit entr${audit.length === 1 ? "y" : "ies"}` : "No control deck actions recorded",
    evidence: audit.length
      ? audit.map((entry) => evidence(entry.actionId || "action", `${entry.result || "unknown"} ${entry.createdAt || ""}`, "audit"))
      : [evidence("audit", "No audit entries yet.")],
    freshness: { generatedAt, source: "audit" },
    recommendedAction: "Use this to verify mutations.",
  };
}

function overviewSignal(signals, generatedAt) {
  const maxSeverity = signals.reduce((current, item) => (SEVERITY_RANK[item.severity] > SEVERITY_RANK[current] ? item.severity : current), "ok");
  const degraded = signals.filter((item) => item.status === "degraded").length;
  return {
    id: "overview",
    lane: "overview",
    title: "Mac Mini Control Deck",
    status: degraded ? "degraded" : "ok",
    severity: maxSeverity,
    verdict: degraded ? `${degraded} degraded signal${degraded === 1 ? "" : "s"}` : "All collected signals available",
    evidence: [evidence("signals", `${signals.length} signals collected`)],
    freshness: { generatedAt, source: "control-deck" },
    recommendedAction: degraded ? "Review degraded signals before acting." : "No immediate action.",
  };
}

function normalizeSnapshot(generatedAt, signals) {
  const lanes = Object.fromEntries(SNAPSHOT_LANES.map((lane) => [lane, []]));
  for (const item of [overviewSignal(signals, generatedAt), ...signals]) {
    lanes[item.lane].push(item);
  }
  const allSignals = Object.values(lanes).flat();
  const severity = allSignals.reduce((current, item) => (SEVERITY_RANK[item.severity] > SEVERITY_RANK[current] ? item.severity : current), "ok");
  const degraded = allSignals.filter((item) => item.status === "degraded");
  return {
    kind: "ControlDeckSnapshot",
    version: 1,
    generatedAt,
    severity,
    verdict: degraded.length ? `${degraded.length} degraded signal${degraded.length === 1 ? "" : "s"}` : "Control deck snapshot collected",
    evidence: allSignals.flatMap((item) => item.evidence || []).slice(0, 80),
    freshness: { generatedAt, source: "control-deck" },
    recommendedAction: degraded.length ? "Use previews and verification before operational changes." : "No immediate action.",
    lanes,
  };
}

async function collectControlDeckSnapshot(workspaceRoot, options = {}) {
  const generatedAt = nowFromOptions(options).toISOString();
  const signals = [
    ...collectDiskSignals(generatedAt),
    collectLaunchAgentSignals(generatedAt),
    await collectProcessSignal(workspaceRoot, generatedAt, options),
    await collectToolVersionSignals(workspaceRoot, generatedAt, options),
    await collectBackupSignal(workspaceRoot, generatedAt, options),
    await collectOrionStatusSignal(workspaceRoot, generatedAt, options),
    await collectRepoSignal(workspaceRoot, generatedAt, options),
    collectCleanupSignal(workspaceRoot, generatedAt),
    collectActivitySignal(workspaceRoot, generatedAt),
  ];
  return normalizeSnapshot(generatedAt, signals);
}

function getControlDeckActions() {
  return ACTIONS.map((action) => ({ ...action }));
}

function requireAction(actionId) {
  const action = ACTIONS.find((candidate) => candidate.id === String(actionId || ""));
  if (!action) {
    return null;
  }
  return action;
}

function candidateById(workspaceRoot, candidateId) {
  return listCleanupCandidates(workspaceRoot).find((candidate) => candidate.id === String(candidateId || "")) || null;
}

function readManifest(workspaceRoot) {
  const manifest = readJson(manifestPath(workspaceRoot), { version: 1, items: [] });
  return {
    version: 1,
    items: Array.isArray(manifest.items) ? manifest.items : [],
  };
}

function writeManifest(workspaceRoot, manifest) {
  writeJsonAtomic(manifestPath(workspaceRoot), {
    version: 1,
    updatedAt: new Date().toISOString(),
    items: Array.isArray(manifest.items) ? manifest.items : [],
  });
}

function confirmationMatches(value, expected) {
  return value === true || String(value || "").trim().toUpperCase() === expected;
}

async function previewControlDeckAction(workspaceRoot, actionId, body = {}) {
  const action = requireAction(actionId);
  if (!action) return { ok: false, error: "unknown-action", actionId: String(actionId || ""), mutation: false };
  if (action.id === "refresh-snapshot") {
    return { ok: true, actionId: action.id, mutation: false, snapshot: await collectControlDeckSnapshot(workspaceRoot) };
  }
  if (action.id === "acknowledge-issue") {
    return { ok: true, actionId: action.id, mutation: false, issueId: String(body.issueId || ""), message: "Acknowledge records only on approve." };
  }
  if (action.id === "preview-cleanup" || action.id === "quarantine-cleanup") {
    const candidate = candidateById(workspaceRoot, body.candidateId);
    if (!candidate) return { ok: false, error: "candidate-not-found", actionId: action.id, mutation: false };
    return { ok: true, actionId: action.id, mutation: false, candidate };
  }
  if (action.id === "restore-quarantine") {
    const itemId = String(body.itemId || "").trim();
    const item = readManifest(workspaceRoot).items.find((candidate) => candidate.id === itemId) || null;
    if (!item) return { ok: false, error: "quarantine-item-not-found", actionId: action.id, mutation: false };
    return { ok: true, actionId: action.id, mutation: false, item };
  }
  return { ok: false, error: "unsupported-action", actionId: action.id, mutation: false };
}

function movePath(source, target) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  try {
    fs.renameSync(source, target);
  } catch (error) {
    if (error && error.code !== "EXDEV") throw error;
    fs.cpSync(source, target, { recursive: true, force: false, errorOnExist: true });
    fs.rmSync(source, { recursive: true, force: true });
  }
}

async function quarantineCleanupCandidate(workspaceRoot, body = {}) {
  const candidate = candidateById(workspaceRoot, body.candidateId);
  if (!candidate) return { ok: false, error: "candidate-not-found", actionId: "quarantine-cleanup", mutation: false };
  if (!confirmationMatches(body.confirm || body.confirmation || body.approved, "QUARANTINE")) {
    return { ok: false, error: "confirmation-required", actionId: "quarantine-cleanup", mutation: false };
  }
  const itemId = hashId(`${candidate.path}:${Date.now()}:${Math.random()}`, "quarantine");
  const target = path.join(quarantineRoot(workspaceRoot), "items", itemId, path.basename(candidate.path));
  try {
    movePath(candidate.path, target);
    const item = {
      id: itemId,
      candidateId: candidate.id,
      originalPath: candidate.path,
      quarantinePath: target,
      relativePath: candidate.relativePath,
      type: candidate.type,
      bytes: candidate.bytes,
      createdAt: new Date().toISOString(),
      status: "quarantined",
    };
    const manifest = readManifest(workspaceRoot);
    manifest.items.unshift(item);
    writeManifest(workspaceRoot, manifest);
    writeAudit(workspaceRoot, {
      actionId: "quarantine-cleanup",
      candidateId: candidate.id,
      itemId,
      result: "ok",
      originalPath: candidate.relativePath,
    });
    return { ok: true, actionId: "quarantine-cleanup", mutation: true, item };
  } catch (error) {
    writeAudit(workspaceRoot, {
      actionId: "quarantine-cleanup",
      candidateId: candidate.id,
      result: "failed",
      error: safeDetail(error instanceof Error ? error.message : String(error || "failed")),
    });
    return { ok: false, error: "quarantine-failed", detail: safeDetail(error instanceof Error ? error.message : String(error || "failed")), mutation: false };
  }
}

function legacyQuarantineItem(workspaceRoot, itemId) {
  const root = path.join(controlDeckStateDir(workspaceRoot), "quarantine");
  let batchDirs = [];
  try {
    batchDirs = fs.readdirSync(root).map((name) => path.join(root, name));
  } catch {
    return null;
  }
  for (const batchDir of batchDirs) {
    const manifest = readJson(path.join(batchDir, "manifest.json"), null);
    const items = manifest && Array.isArray(manifest.items) ? manifest.items : [];
    const item = items.find((candidate) => String(candidate.itemId || candidate.id || "") === String(itemId || ""));
    if (item) {
      return {
        id: String(item.itemId || item.id || ""),
        originalPath: String(item.originalPath || ""),
        quarantinePath: String(item.quarantinedPath || item.quarantinePath || ""),
        relativePath: path.relative(repoRootFromWorkspace(workspaceRoot), String(item.originalPath || "")),
        status: "quarantined",
        legacy: true,
      };
    }
  }
  return null;
}

function restoreQuarantineItem(workspaceRoot, itemId, body = {}) {
  const bodyObject = body && typeof body === "object" ? body : {};
  if (
    Object.keys(bodyObject).length &&
    !confirmationMatches(bodyObject.confirm || bodyObject.confirmation || bodyObject.approved, "RESTORE")
  ) {
    return { ok: false, error: "confirmation-required", actionId: "restore-quarantine", mutation: false };
  }
  const manifest = readManifest(workspaceRoot);
  const item = manifest.items.find((candidate) => candidate.id === String(itemId || "")) || legacyQuarantineItem(workspaceRoot, itemId);
  if (!item || item.status !== "quarantined") {
    return { ok: false, error: "quarantine-item-not-found", actionId: "restore-quarantine", mutation: false };
  }
  if (!fs.existsSync(item.quarantinePath)) {
    return { ok: false, error: "quarantine-path-missing", actionId: "restore-quarantine", mutation: false };
  }
  if (fs.existsSync(item.originalPath)) {
    return { ok: false, error: "original-path-exists", actionId: "restore-quarantine", mutation: false };
  }
  try {
    movePath(item.quarantinePath, item.originalPath);
    item.status = "restored";
    item.restoredAt = new Date().toISOString();
    writeManifest(workspaceRoot, manifest);
    writeAudit(workspaceRoot, {
      actionId: "restore-quarantine",
      itemId: item.id,
      result: "ok",
      originalPath: item.relativePath,
    });
    return {
      ok: true,
      actionId: "restore-quarantine",
      mutation: true,
      status: "succeeded",
      message: "Restored from quarantine.",
      item,
    };
  } catch (error) {
    writeAudit(workspaceRoot, {
      actionId: "restore-quarantine",
      itemId: item.id,
      result: "failed",
      error: safeDetail(error instanceof Error ? error.message : String(error || "failed")),
    });
    return { ok: false, error: "restore-failed", detail: safeDetail(error instanceof Error ? error.message : String(error || "failed")), mutation: false };
  }
}

function actionDescriptors() {
  return getControlDeckActions().map((action) => ({
    id: action.id,
    title: action.label,
    lane:
      action.id.includes("cleanup") || action.id.includes("quarantine")
        ? "cleanup"
        : action.id === "acknowledge-issue"
          ? "activity"
          : "overview",
    description: action.label,
    risk: action.mutates ? "medium" : "low",
    requiresApproval: Boolean(action.mutates),
    enabled: true,
  }));
}

async function controlDeckSnapshot(workspaceRoot, options = {}) {
  const snapshot = await collectControlDeckSnapshot(workspaceRoot, options);
  const laneSignals = (lane) => (snapshot.lanes && Array.isArray(snapshot.lanes[lane]) ? snapshot.lanes[lane] : []);
  const toneFromSeverity = (severity) =>
    severity === "critical" ? "alert" : severity === "warning" ? "warn" : severity === "info" ? "neutral" : "good";
  const health = (item) => ({
    id: item.id,
    label: item.title,
    status: item.verdict || item.status,
    tone: toneFromSeverity(item.severity),
    detail: (item.evidence || []).map((entry) => `${entry.label}: ${entry.detail}`).join(" | "),
    value: item.status,
    updatedAt: item.freshness && item.freshness.generatedAt ? item.freshness.generatedAt : snapshot.generatedAt,
    nextStep: item.recommendedAction || null,
  });
  const cleanupSignal = laneSignals("cleanup").find((item) => Array.isArray(item.candidates));
  const cleanup = (cleanupSignal && cleanupSignal.candidates ? cleanupSignal.candidates : []).map((candidate) => ({
    id: candidate.id,
    label: candidate.relativePath || path.basename(candidate.path || candidate.id),
    kind: candidate.type || "generated",
    path: candidate.path,
    description: candidate.reason || "Repo-local generated cleanup candidate.",
    sizeBytes: candidate.bytes || 0,
    risk: "low",
    preview: `${candidate.relativePath || candidate.path} (${candidate.bytes || 0} bytes)`,
  }));
  const repoEvidence = laneSignals("repos").flatMap((item) => item.evidence || []);
  const repos = repoEvidence.map((entry) => ({
    id: `repo-${entry.label}`,
    name: entry.label,
    path: entry.label,
    branch: null,
    status: entry.detail,
    tone: /clean/i.test(entry.detail) ? "good" : "warn",
    dirty: !/clean/i.test(entry.detail),
    ahead: 0,
    behind: 0,
    detail: entry.detail,
    updatedAt: snapshot.generatedAt,
  }));
  const launchAgents = laneSignals("workstation")
    .filter((item) => item.id === "launchagents")
    .flatMap((item) => item.evidence || [])
    .map((entry) => ({
      id: `launch-${entry.label}`,
      label: entry.label,
      status: "observed",
      tone: "neutral",
      loaded: true,
      running: null,
      pid: null,
      lastExitStatus: null,
      detail: entry.detail,
      updatedAt: snapshot.generatedAt,
    }));
  const allHealth = Object.keys(snapshot.lanes || {})
    .flatMap((lane) => laneSignals(lane))
    .map(health);
  return {
    generatedAt: snapshot.generatedAt,
    verdict: {
      title: snapshot.severity === "critical" ? "Mac Mini needs intervention" : snapshot.severity === "warning" ? "Mac Mini has items to review" : "Mac Mini is steady",
      summary: snapshot.verdict,
      tone: toneFromSeverity(snapshot.severity),
      updatedAt: snapshot.generatedAt,
    },
    attentionItems: allHealth.filter((item) => item.tone === "warn" || item.tone === "alert").slice(0, 12),
    workstation: laneSignals("workstation").map(health),
    orion: laneSignals("orion").map(health),
    repos,
    launchAgents,
    cleanup,
    activity: readControlDeckAudit(workspaceRoot, 20).map((entry, index) => ({
      id: String(entry.id || `${entry.createdAt || "audit"}-${index}`),
      at: String(entry.createdAt || new Date().toISOString()),
      type: String(entry.actionId || "audit"),
      title: String(entry.actionId || "Control Deck event"),
      detail: String(entry.result || entry.error || ""),
      actionId: String(entry.actionId || ""),
      actor: String(entry.actor || ""),
      status: entry.result === "failed" ? "failed" : "succeeded",
    })),
  };
}

function auditEvents(workspaceRoot, limit = 100) {
  return readControlDeckAudit(workspaceRoot, limit).map((entry, index) => ({
    id: String(entry.id || `${entry.createdAt || "audit"}-${index}`),
    at: String(entry.createdAt || new Date().toISOString()),
    type: String(entry.actionId || "audit"),
    title: String(entry.actionId || "Control Deck event"),
    detail: String(entry.result || entry.error || ""),
    actionId: String(entry.actionId || ""),
    actor: String(entry.actor || ""),
    status: entry.result === "failed" ? "failed" : "succeeded",
  }));
}

async function previewAction(workspaceRoot, actionId, body = {}) {
  const action = requireAction(actionId);
  if (!action) {
    return {
      actionId: String(actionId || ""),
      blocked: true,
      blockedReason: "unknown-action",
      mutation: false,
    };
  }
  if (action.id === "preview-cleanup" && Array.isArray(body.candidateIds)) {
    const allowed = new Set(body.candidateIds.map((id) => String(id || "")));
    const candidates = listCleanupCandidates(workspaceRoot)
      .filter((candidate) => allowed.has(candidate.id))
      .map((candidate) => ({
        id: candidate.id,
        label: candidate.relativePath || path.basename(candidate.path || candidate.id),
        kind: candidate.type || "generated",
        path: candidate.path,
        description: candidate.reason,
        sizeBytes: candidate.bytes,
        risk: "low",
        preview: candidate.relativePath,
      }));
    return {
      actionId: action.id,
      title: "Preview Cleanup",
      summary: `${allowed.size} selected cleanup candidate${allowed.size === 1 ? "" : "s"}. No files will move.`,
      risk: "low",
      requiresApproval: false,
      mutation: false,
      candidates,
      changes: candidates.map((candidate) => `${candidate.label}: ${candidate.sizeBytes || 0} bytes`),
    };
  }
  return previewControlDeckAction(workspaceRoot, action.id, body);
}

async function approveAction(workspaceRoot, actionId, body = {}) {
  const action = requireAction(actionId);
  if (!action) {
    return {
      actionId: String(actionId || ""),
      status: "blocked",
      message: "Action is not allowlisted.",
      mutation: false,
    };
  }
  const payload = await approveControlDeckAction(workspaceRoot, action.id, body);
  return {
    ...payload,
    actionId: action.id,
    runId: payload.runId || hashId(`${action.id}:${Date.now()}`, "run"),
    status: payload.status || (payload.ok ? "succeeded" : payload.error === "confirmation-required" ? "blocked" : "failed"),
    message:
      payload.message ||
      (payload.ok
        ? action.id === "quarantine-cleanup"
          ? "Moved selected cleanup candidate into quarantine."
          : "Action completed."
        : payload.error || "Action failed."),
    restoreToken: payload.restoreToken || (payload.item && payload.item.id ? payload.item.id : null),
    output: payload.item ? [payload.item.relativePath || payload.item.originalPath || "updated"] : payload.output || [],
  };
}

function localToken(workspaceRoot) {
  return getOrCreateLoopbackToken(workspaceRoot);
}

function validateLocalToken(req, workspaceRoot) {
  const remoteAddress = String(req && req.socket && req.socket.remoteAddress ? req.socket.remoteAddress : "");
  if (remoteAddress && !["127.0.0.1", "::1", "::ffff:127.0.0.1"].includes(remoteAddress)) return false;
  let queryToken = null;
  try {
    const url = new URL(req.url || "/", `http://${(req.headers && req.headers.host) || "127.0.0.1"}`);
    queryToken = url.searchParams.get("controlDeckToken") || url.searchParams.get("token");
  } catch {
    queryToken = null;
  }
  return validateLoopbackToken(workspaceRoot, (req && req.headers) || {}, queryToken);
}

function isLoopbackRequest(req) {
  const remoteAddress = String(req && req.socket && req.socket.remoteAddress ? req.socket.remoteAddress : "");
  return !remoteAddress || ["127.0.0.1", "::1", "::ffff:127.0.0.1"].includes(remoteAddress);
}

function localTokenCookie(workspaceRoot) {
  const token = getOrCreateLoopbackToken(workspaceRoot);
  return `orion_control_deck_token=${encodeURIComponent(token)}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400`;
}

async function approveControlDeckAction(workspaceRoot, actionId, body = {}) {
  const action = requireAction(actionId);
  if (!action) return { ok: false, error: "unknown-action", actionId: String(actionId || ""), mutation: false };
  if (action.id === "refresh-snapshot") {
    return { ok: true, actionId: action.id, mutation: false, snapshot: await collectControlDeckSnapshot(workspaceRoot) };
  }
  if (action.id === "acknowledge-issue") {
    const issueId = String(body.issueId || "").trim();
    writeAudit(workspaceRoot, {
      actionId: "acknowledge-issue",
      issueId,
      result: "ok",
      actor: safeDetail(body.actor || "unknown", 120),
    });
    return { ok: true, actionId: action.id, mutation: false, issueId };
  }
  if (action.id === "preview-cleanup") {
    return previewControlDeckAction(workspaceRoot, action.id, body);
  }
  if (action.id === "quarantine-cleanup") {
    return quarantineCleanupCandidate(workspaceRoot, body);
  }
  if (action.id === "restore-quarantine") {
    return restoreQuarantineItem(workspaceRoot, body.itemId, body);
  }
  return { ok: false, error: "unsupported-action", actionId: action.id, mutation: false };
}

function getOrCreateLoopbackToken(workspaceRoot) {
  const filePath = tokenPath(workspaceRoot);
  try {
    const existing = fs.readFileSync(filePath, "utf8").trim();
    if (existing.length >= 24) return existing;
  } catch {
    // Create below.
  }
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const token = crypto.randomBytes(32).toString("base64url");
  fs.writeFileSync(filePath, `${token}\n`, { encoding: "utf8", mode: 0o600 });
  try {
    fs.chmodSync(filePath, 0o600);
  } catch {
    // Best effort on filesystems that do not support chmod.
  }
  return token;
}

function timingSafeEqualString(a, b) {
  const left = Buffer.from(String(a || ""));
  const right = Buffer.from(String(b || ""));
  if (left.length !== right.length || !left.length) return false;
  return crypto.timingSafeEqual(left, right);
}

function validateLoopbackToken(workspaceRoot, headers = {}, queryToken = null) {
  let expected = "";
  try {
    expected = fs.readFileSync(tokenPath(workspaceRoot), "utf8").trim();
  } catch {
    return false;
  }
  const headerValue = String(
    headers.authorization || headers.Authorization || headers["x-control-deck-token"] || headers["x-orion-local-token"] || ""
  ).trim();
  const bearer = headerValue.toLowerCase().startsWith("bearer ") ? headerValue.slice(7).trim() : headerValue;
  const cookieToken = String(headers.cookie || "")
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith("orion_control_deck_token="));
  const cookieValue = cookieToken ? decodeURIComponent(cookieToken.slice("orion_control_deck_token=".length)) : "";
  const provided = String(queryToken || bearer || cookieValue || "").trim();
  return timingSafeEqualString(provided, expected);
}

module.exports = {
  actionDescriptors,
  approveControlDeckAction,
  approveAction,
  auditEvents,
  collectControlDeckSnapshot,
  controlDeckSnapshot,
  getControlDeckActions,
  getOrCreateLoopbackToken,
  isLoopbackRequest,
  listCleanupCandidates,
  localToken,
  localTokenCookie,
  previewAction,
  previewControlDeckAction,
  readControlDeckAudit,
  restoreQuarantineItem,
  validateLocalToken,
  validateLoopbackToken,
};
