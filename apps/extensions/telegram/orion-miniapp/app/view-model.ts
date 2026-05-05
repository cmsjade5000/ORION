import type {
  ActivityItem,
  HomePayload,
  InboxPayload,
  JobItem,
  MiniAppScreen,
  QueueFilter,
  QueueRequest,
  QueueRequestStatus,
  ReviewPayload,
  Task,
  TaskStatus,
} from "./types";

const TASK_STATUS_ORDER: TaskStatus[] = ["running", "needs_input", "waiting", "queued", "failed", "done", "stuck"];
const ATTENTION_STATUSES: ReadonlySet<TaskStatus> = new Set(["needs_input", "waiting", "failed"]);
const DONE_STATUSES: ReadonlySet<TaskStatus> = new Set(["done", "failed"]);

function parseStartappTaskId(value: string): string | null {
  const normalized = String(value || "").trim();
  const direct = normalized.match(/^(?:task:|task\/|task)(.+)$/i);
  if (!direct) return null;
  return direct[1].trim() || null;
}

export function screenFromStartapp(startapp?: string): MiniAppScreen {
  const value = String(startapp || "").trim().toLowerCase();
  if (parseStartappTaskId(value)) return "task";
  if (["home", "home-screen", "command", "console", "today", "followups", "review"].includes(value)) return "home";
  if (["compose", "chat", "request", "new"].includes(value)) return "compose";
  if (["queue", "work", "tasks", "inbox", "approvals"].includes(value)) return "queue";
  if (["activity", "logs", "activitylog", "feed", "recent"].includes(value)) return "activity";
  if (["status", "system", "health"].includes(value)) return "status";
  if (["settings", "diagnostics"].includes(value)) return "settings";
  return "home";
}

export function screenTitle(screen: MiniAppScreen): string {
  if (screen === "compose") return "Compose Request";
  if (screen === "queue") return "Task Queue";
  if (screen === "task") return "Task Detail";
  if (screen === "status") return "System Status";
  if (screen === "activity") return "Recent Activity";
  if (screen === "settings") return "Settings";
  return "Home";
}

export function parseTaskIdFromStartapp(startapp?: string): string | null {
  return parseStartappTaskId(String(startapp || "").trim());
}

export function formatRelativeTime(ageMs: number): string {
  const minutes = Math.max(1, Math.round(ageMs / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export function statusTone(status?: string): "good" | "warn" | "alert" | "neutral" {
  const value = String(status || "").toLowerCase();
  if (value.includes("complete") || value.includes("succeeded")) return "good";
  if (value.includes("blocked") || value.includes("failed")) return "alert";
  if (value.includes("pending")) return "warn";
  return "neutral";
}

export function isFollowupActionable(job: JobItem): boolean {
  const state = String(job.state || "").toLowerCase();
  return state === "blocked" || state === "pending_verification";
}

function normalizeTaskStatus(value: string): TaskStatus {
  const normalized = String(value || "").toLowerCase().replace(/[^a-z0-9_]/g, "_");
  if (normalized.includes("queued")) return "queued";
  if (normalized.includes("running") || normalized.includes("active") || normalized.includes("in_progress")) return "running";
  if (normalized.includes("blocked") || normalized.includes("need") || normalized.includes("approval")) return "needs_input";
  if (normalized === "pending_verification" || normalized === "pending") return "needs_input";
  if (normalized.includes("waiting")) return "waiting";
  if (normalized.includes("done") || normalized.includes("completed") || normalized.includes("succeeded")) return "done";
  if (normalized.includes("failed") || normalized.includes("error")) return "failed";
  if (normalized.includes("stuck") || normalized.includes("stalled") || normalized.includes("stagnant")) return "stuck";
  return "queued";
}

function normalizeQueueRequestStatus(status?: QueueRequestStatus | "queuing" | "refresh_delayed"): TaskStatus {
  if (!status) return "queued";
  if (status === "completed") return "done";
  if (status === "failed") return "failed";
  if (status === "queued") return "queued";
  if (status === "refresh_delayed") return "waiting";
  if (status === "acknowledged") return "done";
  return "queued";
}

function normalizeQueueStatusForJob(job: JobItem, queueRequests: QueueRequest[]): TaskStatus {
  const request =
    queueRequests.find((item) => item.jobId === job.job_id && item.status === "queued") ||
    queueRequests.find((item) => item.jobId === job.job_id && item.status === "refresh_delayed") ||
    queueRequests.find((item) => item.jobId === job.job_id && item.status === "failed");
  if (!request) return normalizeTaskStatus(job.state || "");
  return normalizeQueueRequestStatus(request.status);
}

export function buildTaskRows(inbox: InboxPayload | null): Task[] {
  if (!inbox) return [];
  return inbox.jobs.map((job) => {
    const status = normalizeQueueStatusForJob(job, inbox.queueRequests || []);
    return {
      id: job.job_id,
      owner: job.owner,
      objective: job.objective || "No objective provided.",
      state: job.state || "unknown",
      status,
      statusReason: job.state_reason || null,
      inboxPath: job.inbox?.path || null,
    };
  });
}

export function buildActivityFeed(
  home: HomePayload | null,
  inbox: InboxPayload | null,
  queueRequests: QueueRequest[],
  review: ReviewPayload | null
): ActivityItem[] {
  const items: ActivityItem[] = [];
  const seen = new Set<string>();
  const now = Date.now();
  const pushIfUnique = (item: ActivityItem) => {
    if (!seen.has(item.id)) {
      seen.add(item.id);
      items.push(item);
    }
  };

  if (home?.updatedTs) {
    pushIfUnique({
      id: `home-${home.updatedTs}`,
      type: "system",
      title: "System digest refreshed",
      detail: String(home.review || "").slice(0, 140) || "Home snapshot updated.",
      atMs: home.updatedTs,
    });
  }

  if (review?.review) {
    pushIfUnique({
      id: `review-${review.review.length}-${Math.max(0, Math.min(review.review.length, 60))}`,
      type: "system",
      title: "Review update",
      detail: String(review.review).slice(0, 160),
      atMs: now,
    });
  }

  if (inbox?.approvals.length) {
    const approval = inbox.approvals[0];
    pushIfUnique({
      id: `approval-${approval.approvalId}`,
      type: "approval",
      title: "Approval waiting",
      detail: approval.summary || "Approval prompt needs response.",
      atMs: now - approval.ageMs,
    });
  }

  queueRequests.forEach((request, index) => {
    pushIfUnique({
      id: request.id || `queue-${index}-${request.jobId}`,
      type: "task",
      title: `Task queue: ${request.jobId}`,
      detail: request.message || "Queue request event recorded.",
      atMs: Math.max(now - index * 1000 * 60, now - 1000 * 60 * 5),
    });
  });

  return items.sort((a, b) => b.atMs - a.atMs);
}

export function buildQueueRows(tasks: Task[], filter: QueueFilter): Task[] {
  if (filter === "active") {
    return tasks.filter((task) => task.status === "running" || task.status === "queued" || task.status === "waiting").sort(sortTaskByStatus);
  }
  if (filter === "pending") {
    return tasks.filter((task) => task.status === "waiting").sort(sortTaskByStatus);
  }
  if (filter === "needs_input") {
    return tasks.filter((task) => ATTENTION_STATUSES.has(task.status)).sort(sortTaskByStatus);
  }
  if (filter === "done") {
    return tasks.filter((task) => DONE_STATUSES.has(task.status)).sort(sortTaskByStatus);
  }
  if (filter === "failed") {
    return tasks.filter((task) => task.status === "failed").sort(sortTaskByStatus);
  }
  return tasks.slice().sort(sortTaskByStatus);
}

export function statusLabel(status: TaskStatus): string {
  if (status === "needs_input") return "Needs Input";
  if (status === "queued") return "Queued";
  return status.charAt(0).toUpperCase() + status.slice(1).replace("_", " ");
}

export function statusChipClass(status: TaskStatus): "good" | "warn" | "alert" | "neutral" {
  if (status === "done") return "good";
  if (status === "failed") return "alert";
  if (status === "stuck" || status === "needs_input" || status === "waiting") return "warn";
  if (status === "running") return "good";
  return "neutral";
}

function sortTaskByStatus(a: Task, b: Task): number {
  return TASK_STATUS_ORDER.indexOf(a.status) - TASK_STATUS_ORDER.indexOf(b.status);
}

export function isAttentionTask(task: Task): boolean {
  return ATTENTION_STATUSES.has(task.status);
}

export function rightNowCounts(tasks: Task[]) {
  return {
    running: tasks.filter((task) => task.status === "running").length,
    waiting: tasks.filter((task) => task.status === "waiting").length,
    needsInput: tasks.filter((task) => task.status === "needs_input").length,
    done: tasks.filter((task) => task.status === "done").length,
    failed: tasks.filter((task) => task.status === "failed").length,
  };
}
