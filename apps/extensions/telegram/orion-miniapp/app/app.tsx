import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type {
  ActivityItem,
  ApprovalItem,
  BootstrapPayload,
  ChatConversation,
  ChatRunPayload,
  HomePayload,
  InboxPayload,
  JobDetailPayload,
  JobItem,
  MiniAppScreen,
  QueueFilter,
  QueueRequest,
  QueueRequestStatus,
  ReviewPayload,
  Task,
  TaskStatus,
} from "./types";
import {
  applySafeAreaInsets,
  applyTelegramTheme,
  getTelegramWebApp,
  prepareTelegramShell,
  vibrateImpact,
  vibrateNotice,
  vibrateSelection,
} from "./telegram";
import {
  buildActivityFeed,
  buildQueueRows,
  buildTaskRows,
  formatRelativeTime,
  isAttentionTask,
  parseTaskIdFromStartapp,
  rightNowCounts,
  screenFromStartapp,
  screenTitle,
  statusChipClass,
  statusLabel,
} from "./view-model";

type ApiClient = {
  bootstrap(): Promise<BootstrapPayload>;
  home(): Promise<HomePayload>;
  review(): Promise<ReviewPayload>;
  inbox(): Promise<InboxPayload>;
  fetchJobDetail(jobId: string): Promise<JobDetailPayload>;
  sendChat(input: { conversationId: string; message: string }): Promise<ChatRunPayload>;
  fetchRun(runId: string): Promise<ChatRunPayload>;
  streamRun(runId: string, onRun: (payload: ChatRunPayload) => void, onError: (message: string) => void): () => void;
  resolveApproval(approvalId: string, decision: "allow-once" | "allow-always" | "deny"): Promise<{ message: string; closesWebApp?: boolean }>;
  resolveTaskPacketApproval(jobId: string, decision: "approve-once" | "deny"): Promise<{ message: string; duplicate?: boolean }>;
  createFollowup(jobId: string): Promise<{ message: string; request?: QueueRequest; duplicate?: boolean }>;
  updateQueueRequestStatus(requestId: string, status: QueueRequestStatus): Promise<{ request: QueueRequest }>;
};

type BridgeStatus = {
  label: string;
  tone: "good" | "warn" | "alert";
};

type QueueRequestView = Omit<QueueRequest, "status"> & {
  status: QueueRequestStatus | "queuing";
};

type RouteEntry = {
  screen: MiniAppScreen;
  queueFilter?: QueueFilter;
  taskId?: string;
};

const QUEUE_FILTERS: Array<{ id: QueueFilter; label: string }> = [
  { id: "active", label: "Active" },
  { id: "pending", label: "Pending" },
  { id: "needs_input", label: "Needs Input" },
  { id: "done", label: "Done" },
  { id: "failed", label: "Failed" },
];

const QUICK_TEMPLATES = [
  { key: "needs-me", label: "What needs me?", template: "/followups" },
  { key: "plan-today", label: "Plan today", template: "/today" },
  { key: "close-loop", label: "Close the loop", template: "/review" },
  { key: "delegate", label: "Delegate this", template: "/capture " },
  { key: "changed", label: "Explain changes", template: "Explain what changed and what needs my attention." },
];

const QUEUE_TONES: Readonly<Record<TaskStatus | "stalled", "good" | "warn" | "alert" | "neutral">> = {
  done: "good",
  failed: "alert",
  queued: "neutral",
  running: "good",
  waiting: "warn",
  needs_input: "warn",
  stuck: "warn",
  stalled: "warn",
};

function safeNative(action: () => void) {
  try {
    action();
  } catch {
    // Telegram API surface varies and should never break the web UI.
  }
}

function encodeInitDataForUrl(value: string): string {
  return btoa(unescape(encodeURIComponent(value)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function withInitData(url: string): string {
  const tg = getTelegramWebApp();
  if (!tg?.initData) return url;
  const target = new URL(url, window.location.origin);
  target.searchParams.set("initDataB64", encodeInitDataForUrl(tg.initData));
  return target.toString();
}

function jsonFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const tg = getTelegramWebApp();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (tg?.initData) {
    headers["X-Telegram-Init-Data"] = tg.initData;
  }
  return fetch(withInitData(url), {
    ...options,
    headers: {
      ...headers,
      ...(options?.headers || {}),
    },
  }).then(async (response) => {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(String((payload as { error?: string })?.error || `Request failed: ${response.status}`));
    }
    return payload as T;
  });
}

function resolveBridgeStatus(input: {
  loading: boolean;
  error: string;
  sending: boolean;
  home: HomePayload | null;
  review: ReviewPayload | null;
  inbox: InboxPayload | null;
  conversation: ChatConversation | null;
}): BridgeStatus {
  if (input.error) return { label: "Bridge offline", tone: "alert" };
  if (input.loading || input.sending) return { label: "Bridge updating", tone: "warn" };
  if (!input.conversation || !input.home || !input.review || !input.inbox) return { label: "Bridge partial", tone: "warn" };
  return { label: "Bridge online", tone: "good" };
}

type SystemOverview = {
  api: "online" | "partial" | "offline";
  queue: "healthy" | "degraded" | "offline";
  worker: "healthy" | "degraded" | "offline";
  updatedAt: string;
  message: string;
};

function deriveSystemStatus(input: {
  loading: boolean;
  error: string;
  home: HomePayload | null;
  review: ReviewPayload | null;
  inbox: InboxPayload | null;
  queueRequests: QueueRequestView[];
}): SystemOverview {
  if (input.error) {
    return {
      api: "offline",
      queue: "offline",
      worker: "offline",
      updatedAt: new Date().toISOString(),
      message: input.error,
    };
  }

  const updatedFrom = [input.home?.updatedTs, input.inbox?.updatedTs]
    .map((value) => (typeof value === "number" ? value : 0))
    .filter(Boolean);
  const hasPanel = input.loading ? false : Boolean(input.home && input.review && input.inbox);
  const hasFailures = input.queueRequests.some((request) => request.status === "failed");

  return {
    api: hasPanel ? "online" : "partial",
    queue: hasFailures ? "degraded" : input.queueRequests.length ? "healthy" : "healthy",
    worker: hasPanel ? "healthy" : "degraded",
    updatedAt: updatedFrom.length ? new Date(Math.max(...updatedFrom)).toISOString() : new Date().toISOString(),
    message:
      input.loading
        ? "Checking live state"
        : input.error
          ? input.error
          : hasFailures
            ? "Queue has failed packets that may need attention."
            : "Live state is available.",
  };
}

function mergeQueueRequests(current: QueueRequestView[], incoming: QueueRequestView[]): QueueRequestView[] {
  const byId = new Map<string, QueueRequestView>();
  [...incoming, ...current].forEach((request) => {
    byId.set(request.id, request);
  });
  return [...byId.values()].sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt)).slice(0, 20);
}

function summarizeLastRequest(
  tasks: Task[],
  queueRequests: QueueRequestView[],
  conversation: ChatConversation | null,
): { task: Task | null; text: string; request: QueueRequestView | null } {
  const latestQueueItem = queueRequests[0] || null;
  const fromTask = latestQueueItem ? tasks.find((task) => task.id === latestQueueItem.jobId) || null : null;
  if (fromTask) {
    return { task: fromTask, request: latestQueueItem, text: `${fromTask.objective} (${statusLabel(fromTask.status)})` };
  }
  if (!conversation?.messages?.length) {
    return { task: null, request: latestQueueItem, text: "No request has been sent yet." };
  }
  const lastUserMessage = [...conversation.messages].reverse().find((message) => message.role === "user");
  if (!lastUserMessage) {
    return { task: null, request: latestQueueItem, text: "No request has been sent yet." };
  }
  const text = lastUserMessage.text.trim();
  return { task: null, request: latestQueueItem, text: text ? text.slice(0, 96) + (text.length > 96 ? "…" : "") : "No request has been sent yet." };
}

function formatQueueRequestTime(value: string): string {
  const ts = Date.parse(value);
  if (!Number.isFinite(ts)) return "recently";
  return new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function digestPreview(value?: string): string {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) return "No current signal.";
  return text.length > 132 ? `${text.slice(0, 129)}...` : text;
}

type MiniAppViewProps = {
  appName: string;
  route: RouteEntry;
  routeDepth: number;
  bridgeStatus: BridgeStatus;
  canGoBack: boolean;
  loading: boolean;
  error: string;
  actionMessage: string;
  conversation: ChatConversation | null;
  inbox: InboxPayload | null;
  home: HomePayload | null;
  review: ReviewPayload | null;
  tasks: Task[];
  queueFilter: QueueFilter;
  queueRequests: QueueRequestView[];
  activity: ActivityItem[];
  systemStatus: SystemOverview;
  selectedJobDetail: JobDetailPayload | null;
  detailLoading: boolean;
  composerText: string;
  sending: boolean;
  hasNativeMainButton: boolean;
  onNavigate(screen: MiniAppScreen, queueFilter?: QueueFilter): void;
  onBack(): void;
  onComposerChange(text: string): void;
  onComposerSubmit(): void;
  onApproval(approvalId: string, decision: "allow-once" | "allow-always" | "deny"): void;
  onTaskPacketApproval?(jobId: string, decision: "approve-once" | "deny"): void;
  onFollowup(jobId: string): void;
  onAcknowledgeQueueRequest(requestId: string): void;
  onOpenTask(taskId: string): void;
  onClearError(): void;
};

function ChipNav({
  active,
  onChange,
}: {
  active: MiniAppScreen;
  onChange: (screen: MiniAppScreen) => void;
}) {
  const entries: MiniAppScreen[] = ["home", "compose", "queue", "status", "activity", "settings"];
  return (
    <nav className="chip-nav" aria-label="Primary routes">
      {entries.map((screen) => (
        <button
          key={screen}
          type="button"
          className={`chip-nav__btn ${active === screen ? "is-active" : ""}`}
          onClick={() => onChange(screen)}
        >
          {screenTitle(screen)}
        </button>
      ))}
    </nav>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <header className="panel__header">
        <h2>{title}</h2>
        {subtitle ? <p className="panel__subtitle">{subtitle}</p> : null}
      </header>
      {children}
    </section>
  );
}

function CardRow({ children }: { children: ReactNode }) {
  return <div className="card-row">{children}</div>;
}

function StatCard({ label, value, tone, detail }: { label: string; value: string | number; tone?: "good" | "warn" | "alert" | "neutral"; detail?: string }) {
  return (
    <article className={`stat-card tone-${tone || "neutral"}`}>
      <p className="stat-card__label">{label}</p>
      <p className="stat-card__value">{value}</p>
      {detail ? <p className="stat-card__detail">{detail}</p> : null}
    </article>
  );
}

function QueueFilterTabs({ value, onChange }: { value: QueueFilter; onChange: (filter: QueueFilter) => void }) {
  return (
    <div className="filter-tabs" role="tablist" aria-label="Task filters">
      {QUEUE_FILTERS.map((item) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          aria-selected={value === item.id}
          className={`filter-tab ${value === item.id ? "is-active" : ""}`}
          onClick={() => onChange(item.id)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

function TaskRow({
  task,
  onOpen,
  onFollowup,
  request,
}: {
  task: Task;
  request: QueueRequestView | null;
  onOpen: (taskId: string) => void;
  onFollowup: (taskId: string) => void;
}) {
  return (
    <article className="task-row">
      <p className="task-row__meta">{task.owner}</p>
      <h3>{task.objective}</h3>
      <p className={`task-row__status tone-${statusChipClass(task.status)}`}>{statusLabel(task.status)}</p>
      {task.statusReason ? <p className="task-row__reason">{task.statusReason}</p> : null}
      <p className="task-row__id">{task.id}</p>
      <p className="task-row__request">{request ? request.message : "No queued packet yet."}</p>
      <div className="task-row__actions">
        <button type="button" className="button button--primary" onClick={() => onOpen(task.id)}>
          Open Task
        </button>
        {request?.status === "failed" ? (
          <button type="button" className="button" onClick={() => onFollowup(task.id)}>
            Retry Follow-up
          </button>
        ) : null}
      </div>
    </article>
  );
}

function TaskListSection({
  tasks,
  filter,
  queueRequests,
  onOpenTask,
  onFollowup,
}: {
  tasks: Task[];
  filter: QueueFilter;
  queueRequests: QueueRequestView[];
  onOpenTask: (taskId: string) => void;
  onFollowup: (taskId: string) => void;
}) {
  return (
    <Section title="Task Queue" subtitle={`Current view: ${filter}`}>
      {tasks.length ? (
        tasks.map((task) => {
          const request = queueRequests.find((item) => item.jobId === task.id) || null;
          return (
            <TaskRow
              key={task.id}
              task={task}
              onOpen={onOpenTask}
              onFollowup={onFollowup}
              request={request}
            />
          );
        })
      ) : (
        <p className="empty-mini">No tasks match this filter.</p>
      )}
    </Section>
  );
}

function TaskDetailPanel({
  task,
  request,
  detail,
  detailLoading,
  onBack,
  onApproval,
  onTaskPacketApproval,
  onFollowup,
  onAcknowledge,
}: {
  task: Task | null;
  request: QueueRequestView | null;
  detail: JobDetailPayload | null;
  detailLoading: boolean;
  onBack: () => void;
  onApproval: (approvalId: string, decision: "allow-once" | "allow-always" | "deny") => void;
  onTaskPacketApproval?: (jobId: string, decision: "approve-once" | "deny") => void;
  onFollowup: (jobId: string) => void;
  onAcknowledge: () => void;
}) {
  return (
    <Section title="Task Detail" subtitle={task ? task.objective : "Select a task to inspect."}>
      {!task ? <p className="empty-mini">No task selected.</p> : null}
      {task ? (
        <>
          <dl className="detail-grid">
            <div>
              <dt>ID</dt>
              <dd>{task.id}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{statusLabel(task.status)}</dd>
            </div>
            <div>
              <dt>Owner</dt>
              <dd>{task.owner}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>{task.inboxPath || "n/a"}</dd>
            </div>
            {request ? (
              <>
                <div>
                  <dt>Queue packet</dt>
                  <dd>{request.message}</dd>
                </div>
                <div>
                  <dt>Queued</dt>
                  <dd>{formatQueueRequestTime(request.createdAt)}</dd>
                </div>
              </>
            ) : null}
          </dl>
          {detailLoading ? <p className="empty-mini">Loading task context...</p> : null}
          {detail ? (
            <>
              <p className="panel__subtitle">Need Summary</p>
              <p>{detail.needSummary}</p>
              <p className="panel__subtitle">Next Step</p>
              <p>{detail.nextStep}</p>
              {detail.resultLines.length ? <pre className="result-lines">{detail.resultLines.join("\n")}</pre> : null}
              {detail.relatedApprovals.length ? (
                <div>
                  <p className="panel__subtitle">Pending Approvals</p>
                  {detail.relatedApprovals.map((approval) => (
                    <div key={approval.approvalId} className="approval-stack__item">
                      <p>{approval.summary}</p>
                      <div className="task-row__actions">
                        <button
                          type="button"
                          className="button"
                          onClick={() => onApproval(approval.approvalId, "allow-once")}
                        >
                          Allow Once
                        </button>
                        <button
                          type="button"
                          className="button"
                          onClick={() => onApproval(approval.approvalId, "allow-always")}
                        >
                          Allow Always
                        </button>
                        <button
                          type="button"
                          className="button button--ghost"
                          onClick={() => onApproval(approval.approvalId, "deny")}
                        >
                          Deny
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
              {detail.taskPacketApproval?.eligible ? (
                <div>
                  <p className="panel__subtitle">Task Packet Decision</p>
                  <p>{detail.taskPacketApproval.reason}</p>
                  <div className="task-row__actions">
                    <button type="button" className="button" onClick={() => onTaskPacketApproval?.(detail.job.job_id, "approve-once")}>
                      Approve Once
                    </button>
                    <button type="button" className="button button--ghost" onClick={() => onTaskPacketApproval?.(detail.job.job_id, "deny")}>
                      Deny
                    </button>
                  </div>
                </div>
              ) : null}
              {request ? (
                <div className="task-row__actions">
                  <button
                    type="button"
                    className="button"
                    onClick={() => {
                      onFollowup(detail.job.job_id);
                    }}
                  >
                    Ask ORION for rework
                  </button>
                  {request.status === "completed" || request.status === "failed" ? (
                    <button type="button" className="button button--ghost" onClick={onAcknowledge}>
                      Acknowledge Packet
                    </button>
                  ) : null}
                </div>
              ) : null}
            </>
          ) : null}
          <div className="task-row__actions">
            <button type="button" className="button button--primary" onClick={onBack}>
              Back
            </button>
          </div>
        </>
      ) : null}
    </Section>
  );
}

function ActivityPanel({ items }: { items: ActivityItem[] }) {
  return (
    <Section title="Recent Activity">
      {items.length ? (
        <ul className="activity-list">
          {items.slice(0, 20).map((item) => (
            <li key={item.id} className="activity-item">
              <p>
                <span className={`activity-item__type tone-${item.type === "approval" ? "warn" : item.type === "system" ? "good" : "neutral"}`}>
                  {item.type}
                </span>
                {item.title}
              </p>
              <p>{item.detail}</p>
              <p className="activity-item__time">{formatRelativeTime(Math.max(1, Date.now() - item.atMs))}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty-mini">No recent activity yet.</p>
      )}
    </Section>
  );
}

function SettingsPanel() {
  const tg = getTelegramWebApp();
  return (
    <Section title="Settings / Diagnostics">
      <dl className="detail-grid">
        <div>
          <dt>Telegram color scheme</dt>
          <dd>{tg?.colorScheme || "unknown"}</dd>
        </div>
        <div>
          <dt>Main button</dt>
          <dd>{tg?.MainButton ? "Available" : "Unavailable"}</dd>
        </div>
        <div>
          <dt>Back button</dt>
          <dd>{tg?.BackButton ? "Available" : "Unavailable"}</dd>
        </div>
      </dl>
      <p className="panel__subtitle">The app keeps Telegram shell sync explicit and only binds back behavior when there is a real route stack.</p>
    </Section>
  );
}

export function MiniAppView(props: MiniAppViewProps) {
  const filteredQueue = useMemo(
    () => buildQueueRows(props.tasks, props.queueFilter || "active"),
    [props.tasks, props.queueFilter],
  );
  const rightNow = rightNowCounts(props.tasks);
  const attentionTasks = useMemo(() => props.tasks.filter(isAttentionTask), [props.tasks]);
  const lastRequest = summarizeLastRequest(props.tasks, props.queueRequests, props.conversation);

  return (
    <div className="orion-shell">
      <header className="header">
        <div>
          <p className="eyebrow">ORION Relay Console</p>
          <h1>{props.appName}</h1>
        </div>
        <p className={`bridge-status tone-${props.bridgeStatus.tone}`}>{props.bridgeStatus.label}</p>
      </header>

      <ChipNav active={props.route.screen} onChange={(screen) => props.onNavigate(screen)} />

      {props.error ? <p className="banner banner--error">{props.error}</p> : null}
      {props.actionMessage ? <p className="banner banner--info">{props.actionMessage}</p> : null}

      {props.route.screen === "home" ? (
        <main className="layout">
          <Section title="What is Orion doing right now?">
            <CardRow>
              <StatCard label="Running" value={rightNow.running} tone="good" />
              <StatCard label="Waiting" value={rightNow.waiting} tone="warn" />
              <StatCard label="Needs Input" value={rightNow.needsInput} tone="warn" />
            </CardRow>
            <div className="quick-actions">
              <button type="button" className="button button--primary" onClick={() => props.onNavigate("compose")}>
                New Request
              </button>
              <button type="button" className="button" onClick={() => props.onNavigate("queue", "active")}>
                Open Active Queue
              </button>
              <button type="button" className="button" onClick={() => props.onNavigate("status")}>
                Open System Status
              </button>
            </div>
          </Section>

          <Section title="Daily loop" subtitle="Capture, plan, follow up, review.">
            <div className="daily-loop-grid">
              <article className="daily-loop-card">
                <p className="mini-task__status">Today</p>
                <p className="detail-text">{digestPreview(props.review?.today || props.home?.today)}</p>
                <button
                  type="button"
                  className="button"
                  onClick={() => {
                    props.onComposerChange("/today");
                    props.onNavigate("compose");
                  }}
                >
                  Plan Today
                </button>
              </article>
              <article className="daily-loop-card">
                <p className="mini-task__status">Follow-ups</p>
                <p className="detail-text">{digestPreview(props.review?.followups)}</p>
                <button
                  type="button"
                  className="button"
                  onClick={() => {
                    props.onComposerChange("/followups");
                    props.onNavigate("compose");
                  }}
                >
                  What Needs Me?
                </button>
              </article>
              <article className="daily-loop-card">
                <p className="mini-task__status">Review</p>
                <p className="detail-text">{digestPreview(props.review?.review || props.home?.review)}</p>
                <button
                  type="button"
                  className="button"
                  onClick={() => {
                    props.onComposerChange("/review");
                    props.onNavigate("compose");
                  }}
                >
                  Close The Loop
                </button>
              </article>
            </div>
          </Section>

          <Section title="Last request" subtitle="One tap to inspect last request detail.">
            <p className="detail-title">{lastRequest.text}</p>
            {lastRequest.task ? (
              <div className="task-row__actions">
                <button type="button" className="button button--primary" onClick={() => props.onOpenTask(lastRequest.task!.id)}>
                  Open Last Request
                </button>
              </div>
            ) : null}
          </Section>

          <Section title="What needs attention?" subtitle="Needs Input / Failed / Stuck">
            {attentionTasks.length ? (
              <>
                <CardRow>
                  {attentionTasks.slice(0, 3).map((task) => {
                    const request = props.queueRequests.find((item) => item.jobId === task.id);
                    const tone = QUEUE_TONES[task.status] || "warn";
                    return (
                      <article key={task.id} className={`mini-task-tone tone-${tone}`}>
                        <p className={`mini-task__status tone-${statusChipClass(task.status)}`}>{statusLabel(task.status)}</p>
                        <p>{task.objective}</p>
                        {request ? <p className="detail-text">{request.message}</p> : null}
                        <button type="button" className="button button--primary" onClick={() => props.onOpenTask(task.id)}>
                          Open
                        </button>
                      </article>
                    );
                  })}
                </CardRow>
                <div className="task-row__actions">
                  <button type="button" className="button" onClick={() => props.onNavigate("queue", "needs_input")}>
                    Open Attention Queue
                  </button>
                </div>
              </>
            ) : (
              <p className="empty-mini">No tasks need attention.</p>
            )}
          </Section>

          <Section title="System Health" subtitle="API / Queue / Worker">
            <CardRow>
              <StatCard
                label="API"
                value={props.systemStatus.api}
                tone={props.systemStatus.api === "online" ? "good" : "warn"}
                detail={props.systemStatus.message}
              />
              <StatCard label="Queue" value={props.systemStatus.queue} tone={props.systemStatus.queue === "healthy" ? "good" : "warn"} />
              <StatCard
                label="Worker"
                value={props.systemStatus.worker}
                tone={props.systemStatus.worker === "healthy" ? "good" : "warn"}
              />
            </CardRow>
            <p className="meta-text">Updated: {new Date(props.systemStatus.updatedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</p>
          </Section>

          <Section title="Quick templates">
            <div className="quick-actions">
              {QUICK_TEMPLATES.map((template) => (
                <button
                  key={template.key}
                  type="button"
                  className="button"
                  onClick={() => {
                    props.onComposerChange(`${template.template} `);
                    props.onNavigate("compose");
                  }}
                >
                  {template.label}
                </button>
              ))}
            </div>
          </Section>
        </main>
      ) : null}

      {props.route.screen === "compose" ? (
        <main className="layout">
          <Section title="Compose Request" subtitle="One clear send action to Orion.">
            <form
              className="composer"
              onSubmit={(event) => {
                event.preventDefault();
                props.onComposerSubmit();
              }}
            >
              <label htmlFor="orion-composer" className="sr-only">
                New request
              </label>
              <textarea
                id="orion-composer"
                value={props.composerText}
                onChange={(event) => props.onComposerChange(event.target.value)}
                placeholder="Tell ORION exactly what to do next..."
                disabled={props.sending || !props.conversation}
              />
              {!props.hasNativeMainButton ? (
                <button
                  type="submit"
                  className="button button--primary"
                  disabled={props.sending || !props.conversation || !props.composerText.trim()}
                >
                  {props.sending ? "Sending..." : "Send to ORION"}
                </button>
              ) : null}
            </form>
            <p className="panel__subtitle">Template quick start</p>
            <div className="quick-actions">
              {QUICK_TEMPLATES.map((template) => (
                <button
                  key={template.key}
                  type="button"
                  className="button"
                  onClick={() => props.onComposerChange(template.template)}
                >
                  {template.label}
                </button>
              ))}
            </div>
          </Section>
        </main>
      ) : null}

      {props.route.screen === "queue" ? (
        <main className="layout">
          <QueueFilterTabs
            value={props.queueFilter || "active"}
            onChange={(filter) => props.onNavigate("queue", filter)}
          />
          <TaskListSection
            tasks={filteredQueue}
            filter={props.queueFilter || "active"}
            queueRequests={props.queueRequests}
            onOpenTask={props.onOpenTask}
            onFollowup={props.onFollowup}
          />
        </main>
      ) : null}

      {props.route.screen === "task" ? (
        <main className="layout">
          <TaskDetailPanel
            task={
              props.route.taskId ? props.tasks.find((task) => task.id === props.route.taskId) || null : null
            }
            request={props.route.taskId ? props.queueRequests.find((item) => item.jobId === props.route.taskId) || null : null}
            detail={props.selectedJobDetail}
            detailLoading={props.detailLoading}
            onBack={() => props.onBack()}
            onApproval={props.onApproval}
            onTaskPacketApproval={props.onTaskPacketApproval}
            onFollowup={props.onFollowup}
            onAcknowledge={() => {
              const request = props.route.taskId
                ? props.queueRequests.find((item) => item.jobId === props.route.taskId)
                : null;
              if (request) props.onAcknowledgeQueueRequest(request.id);
            }}
          />
        </main>
      ) : null}

      {props.route.screen === "status" ? (
        <main className="layout">
          <Section title="System Status" subtitle="Live diagnostics for the Orion relay">
            <div className="detail-grid detail-grid--wide">
              <div>
                <dt>API</dt>
                <dd>{props.systemStatus.api}</dd>
              </div>
              <div>
                <dt>Queue</dt>
                <dd>{props.systemStatus.queue}</dd>
              </div>
              <div>
                <dt>Worker</dt>
                <dd>{props.systemStatus.worker}</dd>
              </div>
              <div>
                <dt>Queue packets</dt>
                <dd>{props.queueRequests.length}</dd>
              </div>
              <div>
                <dt>Last update</dt>
                <dd>{new Date(props.systemStatus.updatedAt).toLocaleString()}</dd>
              </div>
            </div>
            <p className="panel__subtitle">{props.systemStatus.message}</p>
          </Section>
        </main>
      ) : null}

      {props.route.screen === "activity" ? (
        <main className="layout">
          <ActivityPanel items={props.activity} />
        </main>
      ) : null}

      {props.route.screen === "settings" ? (
        <main className="layout">
          <SettingsPanel />
        </main>
      ) : null}
    </div>
  );
}

export function createApiClient(): ApiClient {
  return {
    bootstrap: () => jsonFetch("/api/bootstrap"),
    home: () => jsonFetch("/api/home"),
    review: () => jsonFetch("/api/review"),
    inbox: () => jsonFetch("/api/inbox"),
    fetchJobDetail: (jobId) => jsonFetch(`/api/inbox/jobs/${encodeURIComponent(jobId)}`),
    sendChat: (input) =>
      jsonFetch("/api/chat/runs", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    fetchRun: (runId) => jsonFetch(`/api/chat/runs/${encodeURIComponent(runId)}`),
    streamRun: (runId, onRun, onError) => {
      const source = new EventSource(withInitData(`/api/chat/runs/${encodeURIComponent(runId)}/events`));
      source.addEventListener("run", (event) => {
        try {
          onRun(JSON.parse(event.data) as ChatRunPayload);
        } catch {
          onError("ORION returned a malformed stream event.");
        }
      });
      source.addEventListener("error", () => {
        onError("Lost bridge event stream. Check in a moment.");
        source.close();
      });
      return () => source.close();
    },
    resolveApproval: (approvalId, decision) =>
      jsonFetch(`/api/approvals/${encodeURIComponent(approvalId)}/action`, {
        method: "POST",
        body: JSON.stringify({ decision }),
      }),
    resolveTaskPacketApproval: (jobId, decision) =>
      jsonFetch(`/api/jobs/${encodeURIComponent(jobId)}/task-approval`, {
        method: "POST",
        body: JSON.stringify({ decision }),
      }),
    createFollowup: (jobId) =>
      jsonFetch(`/api/jobs/${encodeURIComponent(jobId)}/followup`, {
        method: "POST",
      }),
    updateQueueRequestStatus: (requestId, status) =>
      jsonFetch(`/api/queue-requests/${encodeURIComponent(requestId)}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
  };
}

export function MiniApp({ api: providedApi }: { api?: ApiClient }) {
  const client = useMemo(() => providedApi ?? createApiClient(), [providedApi]);
  const tg = useMemo(() => getTelegramWebApp(), []);

  const [bootstrap, setBootstrap] = useState<BootstrapPayload | null>(null);
  const [conversation, setConversation] = useState<ChatConversation | null>(null);
  const [home, setHome] = useState<HomePayload | null>(null);
  const [review, setReview] = useState<ReviewPayload | null>(null);
  const [inbox, setInbox] = useState<InboxPayload | null>(null);
  const [routeStack, setRouteStack] = useState<RouteEntry[]>([{ screen: "home" }]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [composerText, setComposerText] = useState("");
  const [sending, setSending] = useState(false);
  const [selectedJobDetail, setSelectedJobDetail] = useState<JobDetailPayload | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [queueRequests, setQueueRequests] = useState<QueueRequestView[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);

  const streamCleanupRef = useRef<(() => void) | null>(null);
    const followupInFlight = useRef<Set<string>>(new Set());
  const mainButtonClickRef = useRef<() => void>(() => undefined);
  const backButtonClickRef = useRef<() => void>(() => undefined);
  const mainButtonEventRef = useRef<() => void>(() => mainButtonClickRef.current());
  const backButtonEventRef = useRef<() => void>(() => backButtonClickRef.current());

  const currentRoute = routeStack.at(-1) || { screen: "home" };
  const canGoBack = routeStack.length > 1;

  const tasks = useMemo(() => buildTaskRows(inbox), [inbox]);
  const systemStatus = useMemo(() => deriveSystemStatus({ loading, error, home, review, inbox, queueRequests }), [loading, error, home, review, inbox, queueRequests]);
  const bridgeStatus = resolveBridgeStatus({ loading, error, sending, home, review, inbox, conversation });

  useEffect(() => {
    prepareTelegramShell(tg);
    const syncTheme = () => {
      applyTelegramTheme(tg);
      applySafeAreaInsets(tg);
    };
    syncTheme();
    tg?.onEvent?.("themeChanged", syncTheme);
    tg?.onEvent?.("viewportChanged", syncTheme);
    tg?.onEvent?.("safeAreaChanged", syncTheme);
    tg?.onEvent?.("contentSafeAreaChanged", syncTheme);
    return () => {
      tg?.offEvent?.("themeChanged", syncTheme);
      tg?.offEvent?.("viewportChanged", syncTheme);
      tg?.offEvent?.("safeAreaChanged", syncTheme);
      tg?.offEvent?.("contentSafeAreaChanged", syncTheme);
    };
  }, [tg]);

  async function refreshPanels() {
    const [homePayload, reviewPayload, inboxPayload] = await Promise.all([client.home(), client.review(), client.inbox()]);
    setHome(homePayload);
    setReview(reviewPayload);
    setInbox(inboxPayload);
    setQueueRequests((current) => mergeQueueRequests(current, inboxPayload.queueRequests || []));
    setActivity(buildActivityFeed(homePayload, inboxPayload, inboxPayload.queueRequests || [], reviewPayload));
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    client
      .bootstrap()
      .then(async (payload) => {
        if (cancelled) return;
        setBootstrap(payload);
        setConversation(payload.conversation);

        const start = screenFromStartapp(payload.startapp);
        const taskId = parseTaskIdFromStartapp(payload.startapp);
        const nextStack: RouteEntry[] =
          start === "home"
            ? [{ screen: "home" }]
            : start === "task" && taskId
              ? [{ screen: "home" }, { screen: "task", taskId }]
              : [{ screen: "home" }, { screen: start }];
        setRouteStack(nextStack);

        await refreshPanels();
        setError("");
      })
      .catch((bootstrapError) => {
        if (cancelled) return;
        setError(bootstrapError instanceof Error ? bootstrapError.message : "ORION could not bootstrap.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [client]);

  useEffect(() => {
    if (currentRoute.screen !== "task" || !currentRoute.taskId) {
      setSelectedJobDetail(null);
      return;
    }
    setSelectedJobDetail(null);
    setDetailLoading(true);
    client
      .fetchJobDetail(currentRoute.taskId)
      .then((detail) => setSelectedJobDetail(detail))
      .catch((detailError) =>
        setError(detailError instanceof Error ? detailError.message : "Could not load task detail."),
      )
      .finally(() => setDetailLoading(false));
  }, [client, currentRoute.screen, currentRoute.taskId]);

  useEffect(() => {
    const mainButton = tg?.MainButton;
    if (!mainButton) return;

    mainButtonClickRef.current = () => {
      if (currentRoute.screen === "compose" && !sending && conversation && composerText.trim()) {
        void handleSubmit();
      }
    };

    safeNative(() => mainButton.offClick(mainButtonEventRef.current));
    safeNative(() => mainButton.hide());

    if (currentRoute.screen === "compose") {
      safeNative(() => mainButton.setText(sending ? "Sending..." : "Send to ORION"));
      safeNative(() => mainButton.onClick(mainButtonEventRef.current));
      if (composerText.trim() && conversation && !sending) {
        safeNative(() => mainButton.enable?.());
      } else {
        safeNative(() => mainButton.disable?.());
      }
      safeNative(() => mainButton.show());
    }

    return () => {
      safeNative(() => mainButton.offClick(mainButtonEventRef.current));
    };
  }, [conversation, currentRoute.screen, composerText, sending, tg]);

  useEffect(() => {
    const backButton = tg?.BackButton;
    if (!backButton) return;

    backButtonClickRef.current = () => {
      if (canGoBack) {
        handleBack();
      }
    };

    safeNative(() => backButton.offClick(backButtonEventRef.current));
    safeNative(() => backButton.hide());

    if (canGoBack) {
      safeNative(() => backButton.show());
      safeNative(() => backButton.onClick(backButtonEventRef.current));
    }

    return () => {
      safeNative(() => backButton.offClick(backButtonEventRef.current));
    };
  }, [canGoBack, tg]);

  useEffect(() => {
    if (!tg?.MainButton || currentRoute.screen !== "compose") return;
    if (!conversation || !composerText.trim() || sending) {
      safeNative(() => tg?.MainButton?.disable?.());
    } else {
      safeNative(() => tg?.MainButton?.enable?.());
    }
  }, [composerText, conversation, currentRoute.screen, sending, tg]);

  useEffect(() => {
    return () => streamCleanupRef.current?.();
  }, []);

  function updateQueueState(update: (incoming: QueueRequestView[]) => QueueRequestView[]) {
    setQueueRequests((current) => update(current));
  }

  function handleSubmit() {
    const text = composerText.trim();
    if (!text || !conversation || sending) return;
    setSending(true);
    setError("");
    setActionMessage("");
    vibrateImpact(tg, "medium");

    setConversation((current) => {
      if (!current) return current;
      return {
        ...current,
        updatedAt: Date.now(),
        messages: [
          ...current.messages,
          {
            id: `optimistic-${Date.now()}`,
            role: "user",
            text,
            createdAt: Date.now(),
          },
        ],
      };
    });
    setComposerText("");

    client
      .sendChat({ conversationId: conversation.conversationId, message: text })
      .then((run) => {
        applyRun(run);
        streamCleanupRef.current?.();
        streamCleanupRef.current = client.streamRun(
          run.runId,
          (payload) => {
            applyRun(payload);
          },
          (message) => {
            setSending(false);
            setError(message);
            vibrateNotice(tg, "error");
          },
        );
      })
      .catch((submitError) => {
        setSending(false);
        setError(submitError instanceof Error ? submitError.message : "ORION did not accept this request.");
        vibrateNotice(tg, "error");
      });
  }

  function applyRun(run: ChatRunPayload) {
    setConversation(run.conversation);
    if (run.status === "completed") {
      setSending(false);
      vibrateNotice(tg, "success");
      void refreshPanels().catch(() => {});
    }
    if (run.status === "failed") {
      setSending(false);
      setError(run.error || "ORION run failed.");
      vibrateNotice(tg, "error");
    }
  }

  function handleApproval(approvalId: string, decision: "allow-once" | "allow-always" | "deny") {
    setActionMessage("");
    client
      .resolveApproval(approvalId, decision)
      .then((payload) => {
        setActionMessage(
          payload.message + (payload.closesWebApp ? "" : payload.message.includes("Run this manually")
            ? ""
            : " Keep Telegram open and tap again if needed."),
        );
        return refreshPanels().catch((refreshError) => {
          setError(refreshError instanceof Error ? refreshError.message : "Action applied; refresh failed.");
        });
      })
      .then(() => vibrateNotice(tg, "success"))
      .catch((approvalError) => {
        setError(approvalError instanceof Error ? approvalError.message : "Approval action failed.");
        vibrateNotice(tg, "error");
      });
  }

  function handleTaskPacketApproval(jobId: string, decision: "approve-once" | "deny") {
    setActionMessage("");
    setError("");
    client
      .resolveTaskPacketApproval(jobId, decision)
      .then((payload) => {
        setActionMessage(payload.message);
        return refreshPanels().catch((refreshError) => {
          setError(refreshError instanceof Error ? refreshError.message : "Task action applied; refresh failed.");
        });
      })
      .then(() => {
        if (currentRoute.taskId === jobId) {
          return client.fetchJobDetail(jobId).then((detail) => setSelectedJobDetail(detail));
        }
      })
      .then(() => vibrateNotice(tg, "success"))
      .catch((approvalError) => {
        setError(approvalError instanceof Error ? approvalError.message : "Task packet action failed.");
        vibrateNotice(tg, "error");
      });
  }

  function handleFollowup(jobId: string) {
    if (followupInFlight.current.has(jobId)) return;
    followupInFlight.current.add(jobId);
    const alreadyQueued = queueRequests.find((request) => request.jobId === jobId);
    if (alreadyQueued && (alreadyQueued.status === "queued" || alreadyQueued.status === "refresh_delayed")) {
      handleRootNavigate("queue", "active");
      followupInFlight.current.delete(jobId);
      return;
    }

    const optimistic: QueueRequestView = {
      id: `pending-${jobId}`,
      jobId,
      owner: "POLARIS",
      status: "queuing",
      message: "Submitting follow-up request...",
      intakePath: "",
      createdAt: new Date().toISOString(),
    };
    updateQueueState((current) => mergeQueueRequests(current, [optimistic]));

    client
      .createFollowup(jobId)
      .then((payload) => {
        const queued: QueueRequestView = payload.request
          ? { ...payload.request, status: payload.request.status }
          : {
              id: `local-${Date.now()}`,
              jobId,
              owner: "POLARIS",
              status: "queued",
              message: payload.message || "Follow-up queued.",
              intakePath: "",
              createdAt: new Date().toISOString(),
            };
        updateQueueState((current) =>
          mergeQueueRequests(
            current.filter((request) => request.id !== optimistic.id),
            [queued],
          ),
        );
        setActionMessage(payload.message || "Follow-up queued.");
        vibrateNotice(tg, "success");
      })
      .catch((followupError) => {
        const message = followupError instanceof Error ? followupError.message : "Follow-up failed.";
        const failed: QueueRequestView = {
          ...optimistic,
          status: "failed",
          message: /secret|raw|token/i.test(message)
            ? "Follow-up failed. Please retry from task detail."
            : message,
        };
        updateQueueState((current) => mergeQueueRequests(current.filter((request) => request.id !== optimistic.id), [failed]));
        setError("Follow-up action failed.");
        vibrateNotice(tg, "error");
      })
      .finally(() => {
        followupInFlight.current.delete(jobId);
      });
  }

  function handleAcknowledgeQueueRequest(requestId: string) {
    client
      .updateQueueRequestStatus(requestId, "acknowledged")
      .then((payload) => {
        updateQueueState((current) => mergeQueueStates(current, [payload.request]));
        return refreshPanels();
      })
      .then(() => vibrateNotice(tg, "success"))
      .catch((ackError) => {
        setError(ackError instanceof Error ? ackError.message : "Could not acknowledge queue packet.");
        vibrateNotice(tg, "error");
      });
  }

  function mergeQueueStates(current: QueueRequestView[], incoming: QueueRequestView[]) {
    return mergeQueueRequests(current, incoming);
  }

  function handleRootNavigate(screen: MiniAppScreen, queueFilter?: QueueFilter) {
    if (screen === "home") {
      setRouteStack([{ screen: "home" }]);
      return;
    }

    if (screen === "queue") {
      setRouteStack([{ screen: "home" }, { screen: "queue", queueFilter: queueFilter || "active" }]);
      return;
    }

    setRouteStack([{ screen: "home" }, { screen }]);
  }

  function handleOpenTask(taskId: string) {
    setRouteStack((current) => {
      const top = current.at(-1);
      if (top?.screen === "task") {
        if (top.taskId === taskId) return current;
        return [...current.slice(0, -1), { screen: "task", taskId }];
      }
      return [...current, { screen: "task", taskId }];
    });
  }

  function handleBack() {
    if (!canGoBack) return;
    setRouteStack((current) => current.slice(0, -1));
  }

  return (
    <MiniAppView
      appName={bootstrap?.appName || "ORION"}
      route={currentRoute}
      routeDepth={routeStack.length}
      bridgeStatus={bridgeStatus}
      canGoBack={canGoBack}
      loading={loading}
      error={error}
      actionMessage={actionMessage}
      conversation={conversation}
      inbox={inbox}
      home={home}
      review={review}
      tasks={tasks}
      queueFilter={currentRoute.queueFilter || "active"}
      queueRequests={queueRequests}
      activity={activity}
      systemStatus={systemStatus}
      selectedJobDetail={selectedJobDetail}
      detailLoading={detailLoading}
      composerText={composerText}
      sending={sending}
      hasNativeMainButton={Boolean(tg?.MainButton)}
      onNavigate={handleRootNavigate}
      onBack={handleBack}
      onComposerChange={setComposerText}
      onComposerSubmit={() => handleSubmit()}
      onApproval={handleApproval}
      onTaskPacketApproval={handleTaskPacketApproval}
      onFollowup={handleFollowup}
      onAcknowledgeQueueRequest={handleAcknowledgeQueueRequest}
      onOpenTask={handleOpenTask}
      onClearError={() => setError("")}
    />
  );
}
