import { useEffect, useMemo, useRef, useState } from "react";
import type {
  BootstrapPayload,
  ChatConversation,
  ChatRunPayload,
  HomePayload,
  InboxPayload,
  JobDetailPayload,
  JobItem,
  MiniAppScreen,
  QueueRequest,
  QueueRequestStatus,
  ReviewPayload,
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
import { buildInboxSections, formatRelativeTime, isFollowupActionable, screenFromStartapp, screenTitle, statusTone } from "./view-model";

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

const ACTIVE_QUEUE_STATUSES = ["queuing", "queued", "refresh_delayed"] as const;

function normalizeQueueStatus(status?: string): string {
  return String(status || "").trim().toLowerCase();
}

function isActionableQueueStatus(status?: string): boolean {
  return ACTIVE_QUEUE_STATUSES.includes(normalizeQueueStatus(status) as (typeof ACTIVE_QUEUE_STATUSES)[number]);
}

function isAcknowledgableQueueStatus(status?: string): boolean {
  return ["completed", "failed", "refresh_delayed"].includes(normalizeQueueStatus(status));
}

function queueAcknowledgeLabel(): string {
  return "Acknowledge";
}

function safeNative(action: () => void) {
  try {
    action();
  } catch {
    // Telegram native button APIs vary by client/version; keep the web UI alive.
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
      throw new Error(String((payload as any).error || `Request failed: ${response.status}`));
    }
    return payload as T;
  });
}

function friendlyPanelError(error: unknown, fallback: string): string {
  const message = error instanceof Error ? error.message : String(error || "");
  if (/Command failed:|assistant_status\.py|usage:|invalid choice/i.test(message)) {
    return "ORION queued the action, but the status panel refresh hit a backend command mismatch.";
  }
  if (/miniapp-auth:/i.test(message)) {
    return "Telegram bridge auth drifted. Close the Mini App and reopen it from Telegram.";
  }
  if (/job not found/i.test(message)) {
    return "That work item is no longer in the active queue.";
  }
  if (/already queuing/i.test(message)) {
    return "That follow-up is already being queued.";
  }
  return fallback;
}

function mergeQueueRequests(current: QueueRequestView[], incoming: QueueRequestView[]): QueueRequestView[] {
  const byId = new Map<string, QueueRequestView>();
  [...incoming, ...current].forEach((request) => {
    byId.set(request.id, request);
  });
  return [...byId.values()]
    .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt))
    .slice(0, 20);
}

function requestForJob(queueRequests: QueueRequestView[], jobId: string): QueueRequestView | null {
  return (
    queueRequests.find((request) => request.jobId === jobId && isActionableQueueStatus(request.status)) ||
    queueRequests.find((request) => request.jobId === jobId && request.status === "failed") ||
    queueRequests.find((request) => request.jobId === jobId && request.status === "completed") ||
    null
  );
}

function queueStatusLabel(request: QueueRequestView | null): string {
  if (!request) return "Ask POLARIS to Rework";
  if (request.status === "queuing") return "Queuing...";
  if (request.status === "queued") return "Rework Queued";
  if (request.status === "refresh_delayed") return "Queued; Refresh Delayed";
  if (request.status === "completed") return "Rework Completed";
  if (request.status === "acknowledged") return "Acknowledged";
  return "Retry Rework Request";
}

function queueStatusTone(status?: string): "good" | "warn" | "alert" | "neutral" {
  if (status === "queued") return "good";
  if (status === "queuing" || status === "refresh_delayed") return "warn";
  if (status === "failed") return "alert";
  if (status === "completed") return "good";
  if (status === "acknowledged") return "neutral";
  return "neutral";
}

function formatQueueRequestTime(value: string): string {
  const ts = Date.parse(value);
  if (!Number.isFinite(ts)) return "recently";
  return new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function deriveBridgeStatus(input: {
  loading: boolean;
  error: string;
  sending: boolean;
  conversation: ChatConversation | null;
  home: HomePayload | null;
  review: ReviewPayload | null;
  inbox: InboxPayload | null;
}): BridgeStatus {
  if (input.error) return { label: "Bridge offline", tone: "alert" };
  if (input.loading) return { label: "Bridge checking", tone: "warn" };
  if (input.sending) return { label: "Bridge sending", tone: "warn" };
  if (!input.conversation) return { label: "Bridge unavailable", tone: "alert" };
  if (!input.home || !input.review || !input.inbox) return { label: "Bridge partial", tone: "warn" };
  return { label: "Bridge online", tone: "good" };
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
          onError("ORION sent back a garbled bridge update.");
        }
      });
      source.addEventListener("error", () => {
        onError("ORION lost the bridge signal for a moment.");
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

type MiniAppViewProps = {
  appName: string;
  screen: MiniAppScreen;
  screenLabel: string;
  bridgeStatus: BridgeStatus;
  conversation: ChatConversation | null;
  inbox: InboxPayload | null;
  selectedJobDetail: JobDetailPayload | null;
  detailLoading: boolean;
  home: HomePayload | null;
  review: ReviewPayload | null;
  queueRequests: QueueRequestView[];
  loading: boolean;
  error: string;
  composerText: string;
  sending: boolean;
  hasNativeMainButton: boolean;
  actionMessage: string;
  selectedJobId: string | null;
  onScreenChange(screen: MiniAppScreen): void;
  onComposerChange(text: string): void;
  onComposerSubmit(): void;
  onApproval(approvalId: string, decision: "allow-once" | "allow-always" | "deny"): void;
  onTaskPacketApproval?(jobId: string, decision: "approve-once" | "deny"): void;
  onFollowup(jobId: string): void;
  onAcknowledgeQueueRequest(requestId: string): void;
  onSelectJob(jobId: string | null): void;
  onQueueCenter(): void;
};

export function MiniAppView(props: MiniAppViewProps) {
  const sections = props.inbox ? buildInboxSections(props.inbox) : [];
  const visibleQueueRequests = props.queueRequests.filter((request) => request.status !== "acknowledged");
  const selectedJob =
    props.selectedJobId && props.inbox
      ? props.inbox.jobs.find((job) => job.job_id === props.selectedJobId) || null
      : null;
  const latestQueueRequest = visibleQueueRequests[0] || null;

  return (
    <div className="starship-shell">
      <div className="starfield" aria-hidden="true" />
      <header className="hero">
        <div className="hero__row">
          <div>
            <h1>{props.appName}</h1>
            <p className="hero__lede">A friendly bridge into ORION: chat up front, mission inbox on deck, today in view.</p>
          </div>
          <div className={`bridge-status tone-${props.bridgeStatus.tone}`} aria-live="polite">
            <span className="bridge-status__light" aria-hidden="true" />
            <span>{props.bridgeStatus.label}</span>
          </div>
        </div>
      </header>

      <nav className="nav-grid" aria-label="ORION mini app sections">
        {(["chat", "inbox", "today"] as MiniAppScreen[]).map((screen) => (
          <button
            key={screen}
            type="button"
            className={`nav-chip ${props.screen === screen ? "is-active" : ""}`}
            aria-label={`Open ${screenTitle(screen)}`}
            onClick={() => props.onScreenChange(screen)}
          >
            <span className="nav-chip__eyebrow">{screen === "chat" ? "Bridge" : screen === "inbox" ? "Mission" : "Status"}</span>
            <span className="nav-chip__label">{screenTitle(screen)}</span>
          </button>
        ))}
      </nav>

      {props.error ? <div className="banner banner--error">{props.error}</div> : null}
      {props.actionMessage ? <div className="banner banner--info">{props.actionMessage}</div> : null}

      <main className="layout">
        {props.screen === "chat" ? (
          <section className="panel panel--chat">
            <div className="panel__header">
              <div>
                <h2>{props.screenLabel}</h2>
              </div>
            </div>
            <div className="transcript">
              {props.loading ? <div className="empty-state">Booting the bridge console...</div> : null}
              {!props.loading && props.conversation && props.conversation.messages.length === 0 ? (
                <div className="empty-state">
                  <p className="empty-state__title">ORION is on station.</p>
                  <p>Ask for a summary, hand over a task, or queue the next move from the same bridge.</p>
                </div>
              ) : null}
              {props.conversation?.messages.map((message) => (
                <article key={message.id} className={`bubble bubble--${message.role}`}>
                  <div className="bubble__meta">
                    <span>{message.role === "assistant" ? "ORION" : message.role === "user" ? "You" : "Bridge"}</span>
                    <span>{new Date(message.createdAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>
                  </div>
                  <p>{message.text}</p>
                </article>
              ))}
            </div>
            <form
              className="composer"
              onSubmit={(event) => {
                event.preventDefault();
                props.onComposerSubmit();
              }}
            >
              <textarea
                value={props.composerText}
                onChange={(event) => props.onComposerChange(event.target.value)}
                placeholder="Message ORION from the bridge..."
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
          </section>
        ) : null}

        {props.screen === "inbox" ? (
          <section className="panel panel--inbox">
            <div className="panel__header">
              <div>
                <h2>Mission Inbox</h2>
              </div>
              <div className="cluster-pills">
                {sections.map((section) => (
                  <div key={section.key} className="metric-pill">
                    <span>{section.title}</span>
                    <strong>{section.count}</strong>
                  </div>
                ))}
              </div>
            </div>
            <div className="panel-grid">
              <div className="stack">
                <section className="subpanel">
                  <h3>Approvals</h3>
                  {props.inbox?.approvals.length ? (
                    props.inbox.approvals.map((approval) => (
                      <article key={approval.approvalId} className="list-card">
                        <div className="list-card__meta">
                          <span>{approval.label}</span>
                          <span>{formatRelativeTime(approval.ageMs)}</span>
                        </div>
                        <p>{approval.summary}</p>
                        <div className="action-row">
                          <button type="button" className="button button--primary" onClick={() => props.onApproval(approval.approvalId, "allow-once")}>
                            Allow Once
                          </button>
                          <button type="button" className="button" onClick={() => props.onApproval(approval.approvalId, "allow-always")}>
                            Always
                          </button>
                          <button type="button" className="button button--ghost" onClick={() => props.onApproval(approval.approvalId, "deny")}>
                            Deny
                          </button>
                        </div>
                      </article>
                    ))
                  ) : (
                    <div className="empty-mini">No live approval prompts on the board.</div>
                  )}
                </section>

                <section className="subpanel">
                  <h3>Work Queue</h3>
                  {props.inbox?.jobs.length ? (
                    props.inbox.jobs.map((job) => {
                      const queueRequest = requestForJob(props.queueRequests, job.job_id);
                      const queueLocked = queueRequest && isActionableQueueStatus(queueRequest.status);
                      const hasApproval = props.inbox?.approvals.some((approval) =>
                        [approval.summary, approval.label, approval.sessionKey, approval.sessionId]
                          .join(" ")
                          .toLowerCase()
                          .includes(job.job_id.toLowerCase())
                      );
                      return (
                        <article key={job.job_id} className={`list-card tone-${statusTone(job.state)}`}>
                          <div className="list-card__meta">
                            <span>{job.owner}</span>
                            <span>{job.state.replace(/_/g, " ")}</span>
                          </div>
                          <p>{job.objective}</p>
                          <div className="mission-hints">
                            {hasApproval ? <span className="hint-pill tone-warn">Approval needed</span> : null}
                            {job.state_reason ? <span className="hint-pill">{job.state_reason.replace(/_/g, " ")}</span> : null}
                            {job.result?.status ? <span className={`hint-pill tone-${statusTone(job.result.status)}`}>Result {job.result.status}</span> : null}
                          </div>
                          {queueRequest ? (
                            <div className={`queue-chip tone-${queueStatusTone(queueRequest.status)}`}>
                              <strong>{queueStatusLabel(queueRequest)}</strong>
                              {queueRequest.status === "failed" ? <span>{queueRequest.message}</span> : null}
                            </div>
                          ) : null}
                          <div className="action-row">
                            <button type="button" className="button" onClick={() => props.onSelectJob(job.job_id)}>
                              Inspect
                            </button>
                            {isFollowupActionable(job) ? (
                              <button
                                type="button"
                                className="button button--primary"
                                disabled={Boolean(queueLocked)}
                                onClick={() => props.onFollowup(job.job_id)}
                              >
                                {queueStatusLabel(queueRequest)}
                              </button>
                            ) : null}
                            {queueRequest && isAcknowledgableQueueStatus(queueRequest.status) ? (
                              <button
                                type="button"
                                className="button button--ghost"
                                onClick={() => props.onAcknowledgeQueueRequest(queueRequest.id)}
                              >
                                {queueAcknowledgeLabel()}
                              </button>
                            ) : null}
                          </div>
                        </article>
                      );
                    })
                  ) : (
                    <div className="empty-mini">Nothing is clogging the queue right now.</div>
                  )}
                </section>
              </div>

              <aside className="subpanel subpanel--detail">
                <h3>{selectedJob ? "Selected Work Item" : "Queue Notes"}</h3>
                {selectedJob ? (
                  (() => {
                    const queueRequest = requestForJob(props.queueRequests, selectedJob.job_id);
                    const queueLocked = queueRequest && isActionableQueueStatus(queueRequest.status);
                    const detail = props.selectedJobDetail && props.selectedJobDetail.job.job_id === selectedJob.job_id ? props.selectedJobDetail : null;
                    return (
                      <>
                        <p className="detail-title">{selectedJob.objective}</p>
                        {props.detailLoading ? <div className="empty-mini">Loading mission context...</div> : null}
                        {detail ? (
                          <div className="mission-brief">
                            <section>
                              <h4>What It Needs</h4>
                              <p>{detail.needSummary}</p>
                            </section>
                            <section>
                              <h4>Next Move</h4>
                              <p>{detail.nextStep}</p>
                            </section>
                          </div>
                        ) : null}
                        <dl className="detail-grid">
                          <div>
                            <dt>Owner</dt>
                            <dd>{selectedJob.owner}</dd>
                          </div>
                          <div>
                            <dt>State</dt>
                            <dd>{selectedJob.state}</dd>
                          </div>
                          <div>
                            <dt>Inbox</dt>
                            <dd>{selectedJob.inbox?.path || "n/a"}</dd>
                          </div>
                        </dl>
                        {queueRequest ? (
                          <div className={`queue-detail tone-${queueStatusTone(queueRequest.status)}`}>
                            <strong>{queueStatusLabel(queueRequest)}</strong>
                            {queueRequest.intakePath ? <span>{queueRequest.intakePath}</span> : null}
                          </div>
                        ) : null}
                        {queueRequest && isAcknowledgableQueueStatus(queueRequest.status) ? (
                          <div className="action-row">
                            <button
                              type="button"
                              className="button button--ghost"
                              onClick={() => props.onAcknowledgeQueueRequest(queueRequest.id)}
                            >
                              {queueAcknowledgeLabel()} and Close
                            </button>
                          </div>
                        ) : null}
                        {detail?.relatedApprovals.length ? (
                          <div className="approval-stack">
                            <h4>Command Approval</h4>
                            {detail.relatedApprovals.map((approval) => (
                              <article key={approval.approvalId} className="approval-card">
                                <div className="list-card__meta">
                                  <span>{approval.label}</span>
                                  <span>{formatRelativeTime(approval.ageMs)}</span>
                                </div>
                                <p>{approval.summary}</p>
                                <code>{`/approve ${approval.approvalId} ${approval.suggestedDecision}`}</code>
                                <div className="action-row">
                                  <button
                                    type="button"
                                    className="button button--primary"
                                    onClick={() => props.onApproval(approval.approvalId, "allow-once")}
                                  >
                                    Allow Once
                                  </button>
                                  <button type="button" className="button" onClick={() => props.onApproval(approval.approvalId, "allow-always")}>
                                    Always
                                  </button>
                                  <button type="button" className="button button--ghost" onClick={() => props.onApproval(approval.approvalId, "deny")}>
                                    Deny
                                  </button>
                                </div>
                              </article>
                            ))}
                          </div>
                        ) : null}
                        {detail?.taskPacketApproval?.latestDecision ? (
                          <div className="approval-stack">
                            <h4>Task Packet Decision</h4>
                            <article className="approval-card">
                              <div className="list-card__meta">
                                <span>
                                  {detail.taskPacketApproval.latestDecision.decision === "approve_once"
                                    ? "Approved Once"
                                    : "Denied"}
                                </span>
                                <span>{detail.taskPacketApproval.latestDecision.createdAt}</span>
                              </div>
                              <p>{detail.taskPacketApproval.reason}</p>
                              {detail.taskPacketApproval.followupJob ? (
                                <div className="queue-chip tone-good">
                                  <strong>Owner Follow-Up Queued</strong>
                                  <span>
                                    {detail.taskPacketApproval.followupJob.owner} · {detail.taskPacketApproval.followupJob.state.replace(/_/g, " ")} ·{" "}
                                    {detail.taskPacketApproval.followupJob.job_id}
                                  </span>
                                </div>
                              ) : null}
                            </article>
                          </div>
                        ) : null}
                        {detail?.taskPacketApproval?.eligible ? (
                          <div className="approval-stack">
                            <h4>Task Packet Decision</h4>
                            <article className="approval-card">
                              <p>{detail.taskPacketApproval.reason}</p>
                              <div className="action-row">
                                <button
                                  type="button"
                                  className="button button--primary"
                                  onClick={() => props.onTaskPacketApproval?.(selectedJob.job_id, "approve-once")}
                                >
                                  Approve Once
                                </button>
                                <button
                                  type="button"
                                  className="button button--ghost"
                                  onClick={() => props.onTaskPacketApproval?.(selectedJob.job_id, "deny")}
                                >
                                  Deny
                                </button>
                              </div>
                            </article>
                          </div>
                        ) : null}
                        {detail?.resultLines.length ? (
                          <details className="detail-disclosure" open>
                            <summary>Result Evidence</summary>
                            <pre>{detail.resultLines.join("\n")}</pre>
                          </details>
                        ) : null}
                        {detail?.packetText ? (
                          <details className="detail-disclosure">
                            <summary>Original Packet</summary>
                            <pre>{detail.packetText}</pre>
                          </details>
                        ) : null}
                        <div className="action-row">
                          {isFollowupActionable(selectedJob) ? (
                            <button
                              type="button"
                              className={detail?.taskPacketApproval?.eligible ? "button" : "button button--primary"}
                              disabled={Boolean(queueLocked)}
                              onClick={() => props.onFollowup(selectedJob.job_id)}
                            >
                              {queueStatusLabel(queueRequest)}
                            </button>
                          ) : null}
                          {queueRequest ? (
                            <button type="button" className="button" onClick={props.onQueueCenter}>
                              View Queue
                            </button>
                          ) : null}
                          <button type="button" className="button button--ghost" onClick={() => props.onSelectJob(null)}>
                            Close
                          </button>
                        </div>
                      </>
                    );
                  })()
                ) : (
                  <div className="empty-mini">
                    <p>Select a work item to inspect the packet context.</p>
                    <p>Approvals and follow-ups stay limited to existing command paths, not a shadow task system.</p>
                  </div>
                )}
              </aside>
            </div>
            <button type="button" className="queue-activity" onClick={props.onQueueCenter}>
              <span>
                {latestQueueRequest
                  ? `${queueStatusLabel(latestQueueRequest)} · ${formatQueueRequestTime(latestQueueRequest.createdAt)}`
                  : "Queue activity"}
              </span>
              <strong>{visibleQueueRequests.length ? `${visibleQueueRequests.length} recent` : "Open"}</strong>
            </button>
          </section>
        ) : null}

        {props.screen === "queue" ? (
          <section className="panel panel--queue">
            <div className="panel__header">
              <div>
                <h2>Queue Center</h2>
                <p className="panel__note">Recent POLARIS rework requests from this Mini App.</p>
              </div>
              <button type="button" className="button" onClick={() => props.onScreenChange("inbox")}>
                Mission Inbox
              </button>
            </div>
            <div className="queue-list">
              {visibleQueueRequests.length ? (
                visibleQueueRequests.map((request) => (
                  <article key={request.id} className={`list-card queue-card tone-${queueStatusTone(request.status)}`}>
                    <div className="list-card__meta">
                      <span>{request.owner}</span>
                      <span>{formatQueueRequestTime(request.createdAt)}</span>
                    </div>
                    <h3>{queueStatusLabel(request)}</h3>
                    <p>{request.message}</p>
                    <dl className="detail-grid">
                      <div>
                        <dt>Job</dt>
                        <dd>{request.jobId}</dd>
                      </div>
                      <div>
                        <dt>Intake</dt>
                        <dd>{request.intakePath || "pending"}</dd>
                      </div>
                      <div>
                        <dt>Packet</dt>
                        <dd>{request.packetNumber ? `#${request.packetNumber}` : "pending"}</dd>
                      </div>
                    </dl>
                    {isAcknowledgableQueueStatus(request.status) ? (
                      <div className="action-row">
                        <button
                          type="button"
                          className="button button--primary"
                          onClick={() => props.onAcknowledgeQueueRequest(request.id)}
                        >
                          {queueAcknowledgeLabel()} and Close
                        </button>
                      </div>
                    ) : null}
                  </article>
                ))
              ) : (
                <div className="empty-mini">No active queue requests have been created from this Mini App yet.</div>
              )}
            </div>
          </section>
        ) : null}

        {props.screen === "today" ? (
          <section className="panel panel--today">
            <div className="panel__header">
              <div>
                <h2>Today</h2>
              </div>
            </div>
            <div className="today-grid">
              <article className="subpanel">
                <h3>Today Snapshot</h3>
                <pre>{props.home?.today || "No status snapshot yet."}</pre>
              </article>
              <article className="subpanel">
                <h3>Follow-Ups</h3>
                <pre>{props.review?.followups || "No follow-up digest yet."}</pre>
              </article>
              <article className="subpanel">
                <h3>Review</h3>
                <pre>{props.review?.review || props.home?.review || "No review digest yet."}</pre>
              </article>
            </div>
          </section>
        ) : null}
      </main>
    </div>
  );
}

export function MiniApp({ api }: { api?: ApiClient }) {
  const defaultApi = useMemo(() => createApiClient(), []);
  const client = api ?? defaultApi;
  const tg = useMemo(() => getTelegramWebApp(), []);
  const [bootstrap, setBootstrap] = useState<BootstrapPayload | null>(null);
  const [conversation, setConversation] = useState<ChatConversation | null>(null);
  const [home, setHome] = useState<HomePayload | null>(null);
  const [review, setReview] = useState<ReviewPayload | null>(null);
  const [inbox, setInbox] = useState<InboxPayload | null>(null);
  const [screen, setScreen] = useState<MiniAppScreen>("chat");
  const [routeStack, setRouteStack] = useState<MiniAppScreen[]>(["chat"]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [composerText, setComposerText] = useState("");
  const [sending, setSending] = useState(false);
  const [actionMessage, setActionMessage] = useState("");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedJobDetail, setSelectedJobDetail] = useState<JobDetailPayload | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [queueRequests, setQueueRequests] = useState<QueueRequestView[]>([]);
  const streamCleanupRef = useRef<(() => void) | null>(null);
  const followupInFlightRef = useRef(new Set<string>());
  const mainButtonClickRef = useRef<() => void>(() => undefined);
  const backButtonClickRef = useRef<() => void>(() => undefined);
  const mainButtonListenerRef = useRef<() => void>(() => {
    mainButtonClickRef.current();
  });
  const backButtonListenerRef = useRef<() => void>(() => {
    backButtonClickRef.current();
  });
  const lastChatCanSendRef = useRef<boolean | null>(null);
  const selectedJob = selectedJobId && inbox ? inbox.jobs.find((job) => job.job_id === selectedJobId) || null : null;
  const selectedQueueRequest = selectedJob ? requestForJob(queueRequests, selectedJob.job_id) : null;
  const hasBackDestination = selectedJobId !== null || routeStack.length > 1;
  const bridgeStatus = deriveBridgeStatus({ loading, error, sending, conversation, home, review, inbox });

  useEffect(() => {
    prepareTelegramShell(tg);
    const refreshShell = () => {
      applyTelegramTheme(tg);
      applySafeAreaInsets(tg);
    };
    tg?.onEvent?.("themeChanged", refreshShell);
    tg?.onEvent?.("viewportChanged", refreshShell);
    tg?.onEvent?.("safeAreaChanged", refreshShell);
    tg?.onEvent?.("contentSafeAreaChanged", refreshShell);
    return () => {
      tg?.offEvent?.("themeChanged", refreshShell);
      tg?.offEvent?.("viewportChanged", refreshShell);
      tg?.offEvent?.("safeAreaChanged", refreshShell);
      tg?.offEvent?.("contentSafeAreaChanged", refreshShell);
    };
  }, [tg]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    client
      .bootstrap()
      .then((bootstrapPayload) => {
        if (cancelled) return;
        setBootstrap(bootstrapPayload);
        setConversation(bootstrapPayload.conversation);
        const startScreen = screenFromStartapp(bootstrapPayload.startapp);
        setScreen(startScreen);
        setRouteStack([startScreen]);
        setError("");

        return Promise.allSettled([client.home(), client.review(), client.inbox()]).then((results) => {
          if (cancelled) return;
          const [homeResult, reviewResult, inboxResult] = results;
          if (homeResult.status === "fulfilled") {
            setHome(homeResult.value);
          }
          if (reviewResult.status === "fulfilled") {
            setReview(reviewResult.value);
          }
          if (inboxResult.status === "fulfilled") {
            setInbox(inboxResult.value);
            setQueueRequests((current) => mergeQueueRequests(current, inboxResult.value.queueRequests || []));
          }
          if (results.some((result) => result.status === "rejected")) {
            setActionMessage("Bridge chat is live. One of the side panels is still warming up.");
          }
        });
      })
      .catch((loadError) => {
        if (cancelled) return;
        const message = loadError instanceof Error ? loadError.message : "ORION could not boot the bridge.";
        setError(message.startsWith("miniapp-auth:") ? "Telegram bridge auth drifted. Close the Mini App and reopen it from Telegram." : message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  function goToRootScreen(next: MiniAppScreen) {
    if (next === screen) {
      setSelectedJobId(null);
      setSelectedJobDetail(null);
      return;
    }
    setScreen(next);
    setSelectedJobId(null);
    setSelectedJobDetail(null);
    setRouteStack([next]);
  }

  function openQueueCenter() {
    if (screen === "inbox") {
      setSelectedJobId(null);
      setSelectedJobDetail(null);
      setScreen("queue");
      setRouteStack((current) => {
        if (current[current.length - 1] === "queue") return current;
        return [...current, "queue"];
      });
      return;
    }

    setScreen("queue");
    setRouteStack((current) => {
      if (current[current.length - 1] === "queue") return current;
      return [...current, "queue"];
    });
  }

  function goBack() {
    if (screen === "inbox" && selectedJobId) {
      setSelectedJobId(null);
      setSelectedJobDetail(null);
      return;
    }

    if (routeStack.length <= 1) {
      return;
    }

    setRouteStack((current) => {
      if (current.length <= 1) return current;
      const nextStack = current.slice(0, -1);
      const nextScreen = nextStack[nextStack.length - 1];
      setScreen(nextScreen || "chat");
      return nextStack;
    });
  }

  mainButtonClickRef.current = () => {
    if (screen === "chat" && !sending) {
      void handleSubmit();
      return;
    }
    if (screen === "inbox" && selectedJob && isFollowupActionable(selectedJob)) {
      if (selectedQueueRequest?.status === "queuing") return;
      if (selectedQueueRequest && isActionableQueueStatus(selectedQueueRequest.status)) {
        openQueueCenter();
        return;
      }
      void handleFollowup(selectedJob.job_id);
    }
  };
  backButtonClickRef.current = () => {
    goBack();
  };

  useEffect(() => {
    if (!tg?.MainButton || !tg?.BackButton) return;
    const mainButton = tg.MainButton;
    const backButton = tg.BackButton;
    const mainClick = mainButtonListenerRef.current;
    const backClick = backButtonListenerRef.current;

    safeNative(() => mainButton.offClick(mainClick));
    safeNative(() => backButton.offClick(backClick));
    safeNative(() => mainButton.hideProgress?.());
    safeNative(() => mainButton.hide());
    safeNative(() => backButton.hide());

    if (screen === "chat") {
      safeNative(() => mainButton.setText(sending ? "Sending..." : "Send to ORION"));
      lastChatCanSendRef.current = null;
      safeNative(() => mainButton.show());
      safeNative(() => mainButton.onClick(mainClick));
    }
    if (screen === "inbox" && selectedJob && isFollowupActionable(selectedJob)) {
      const isQueued = selectedQueueRequest && isActionableQueueStatus(selectedQueueRequest.status);
      safeNative(() => mainButton.setText(isQueued ? "View Queue" : queueStatusLabel(selectedQueueRequest)));
      if (selectedQueueRequest?.status === "queuing") {
        safeNative(() => mainButton.disable?.());
        safeNative(() => mainButton.showProgress?.(true));
      } else {
        safeNative(() => mainButton.enable?.());
      }
      safeNative(() => mainButton.show());
      safeNative(() => mainButton.onClick(mainClick));
    }
    if (hasBackDestination) {
      safeNative(() => backButton.show());
      safeNative(() => backButton.onClick(backClick));
    } else {
      safeNative(() => backButton.offClick(backClick));
      safeNative(() => backButton.hide());
    }

    return () => {
      safeNative(() => mainButton.hideProgress?.());
      safeNative(() => mainButton.offClick(mainClick));
      safeNative(() => backButton.offClick(backClick));
    };
  }, [screen, selectedJobId, selectedJob, selectedQueueRequest, sending, hasBackDestination, tg]);

  useEffect(() => {
    if (!tg?.MainButton || screen !== "chat") return;
    const canSend = Boolean(composerText.trim() && conversation && !sending);
    if (lastChatCanSendRef.current === canSend) return;
    lastChatCanSendRef.current = canSend;
    if (canSend) {
      safeNative(() => tg.MainButton?.enable?.());
    } else {
      safeNative(() => tg.MainButton?.disable?.());
    }
  }, [composerText, conversation, screen, sending, tg]);

  function applyRun(run: ChatRunPayload) {
    setConversation(run.conversation);
    if (run.status === "completed") {
      setSending(false);
      vibrateNotice(tg, "success");
    }
    if (run.status === "failed") {
      setSending(false);
      setError(run.error || "ORION hit a bridge snag.");
      vibrateNotice(tg, "error");
    }
  }

  async function refreshPanels() {
    const [homePayload, reviewPayload, inboxPayload] = await Promise.all([client.home(), client.review(), client.inbox()]);
    setHome(homePayload);
    setReview(reviewPayload);
    setInbox(inboxPayload);
    setQueueRequests((current) => mergeQueueRequests(current, inboxPayload.queueRequests || []));
  }

  async function handleSubmit() {
    const text = composerText.trim();
    if (!text || sending || !conversation) return;
    setSending(true);
    setError("");
    setActionMessage("");
    vibrateImpact(tg, "medium");

    const optimisticMessage = {
      id: `optimistic-${Date.now()}`,
      role: "user" as const,
      text,
      createdAt: Date.now(),
    };
    setConversation({
      ...conversation,
      updatedAt: Date.now(),
      messages: [...conversation.messages, optimisticMessage],
    });
    setComposerText("");

    try {
      const run = await client.sendChat({
        conversationId: conversation.conversationId,
        message: text,
      });
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
        }
      );
    } catch (submitError) {
      setSending(false);
      setError(submitError instanceof Error ? submitError.message : "ORION could not take the message.");
      vibrateNotice(tg, "error");
    }
  }

  async function handleApproval(approvalId: string, decision: "allow-once" | "allow-always" | "deny") {
    setActionMessage("");
    try {
      const payload = await client.resolveApproval(approvalId, decision);
      setActionMessage(payload.message);
      await refreshPanels();
      vibrateNotice(tg, "success");
      if (payload.closesWebApp) {
        setTimeout(() => tg?.close?.(), 350);
      }
    } catch (approvalError) {
      setError(approvalError instanceof Error ? approvalError.message : "Approval action failed.");
      vibrateNotice(tg, "error");
    }
  }

  async function handleTaskPacketApproval(jobId: string, decision: "approve-once" | "deny") {
    setActionMessage("");
    setError("");
    try {
      const payload = await client.resolveTaskPacketApproval(jobId, decision);
      setActionMessage(payload.message);
      await refreshPanels();
      if (selectedJobId === jobId) {
        setSelectedJobDetail(await client.fetchJobDetail(jobId));
      }
      vibrateNotice(tg, "success");
    } catch (approvalError) {
      setError(approvalError instanceof Error ? approvalError.message : "Task Packet approval failed.");
      vibrateNotice(tg, "error");
    }
  }

  async function handleFollowup(jobId: string) {
    setActionMessage("");
    setError("");
    if (followupInFlightRef.current.has(jobId)) return;
    const existing = requestForJob(queueRequests, jobId);
    if (existing && isActionableQueueStatus(existing.status)) {
      setScreen("queue");
      return;
    }
    followupInFlightRef.current.add(jobId);
    const pendingRequest: QueueRequestView = {
      id: `pending-${jobId}`,
      jobId,
      owner: "POLARIS",
      status: "queuing",
      message: "Asking POLARIS to rework this packet.",
      intakePath: "",
      createdAt: new Date().toISOString(),
    };
    setQueueRequests((current) => mergeQueueRequests(current.filter((request) => request.id !== pendingRequest.id), [pendingRequest]));
    try {
      const payload = await client.createFollowup(jobId);
      const queuedRequest: QueueRequestView =
        payload.request || {
          id: `local-${Date.now()}`,
          jobId,
          owner: "POLARIS",
          status: "queued",
          message: payload.message || "Rework request queued for POLARIS.",
          intakePath: "",
          createdAt: new Date().toISOString(),
        };
      setQueueRequests((current) => mergeQueueRequests(current.filter((request) => request.id !== pendingRequest.id), [queuedRequest]));
      try {
        await refreshPanels();
      } catch (refreshError) {
        const delayedRequest: QueueRequestView = { ...queuedRequest, status: "refresh_delayed" };
        setQueueRequests((current) =>
          mergeQueueRequests(
            current.filter((request) => request.id !== pendingRequest.id && request.id !== queuedRequest.id),
            [delayedRequest]
          )
        );
        void client.updateQueueRequestStatus(queuedRequest.id, "refresh_delayed").catch(() => undefined);
      }
      vibrateNotice(tg, "success");
    } catch (followupError) {
      const failedMessage = friendlyPanelError(followupError, "Follow-up action failed.");
      setQueueRequests((current) =>
        mergeQueueRequests(
          current.filter((request) => request.id !== pendingRequest.id),
          [{ ...pendingRequest, status: "failed", message: failedMessage }]
        )
      );
      vibrateNotice(tg, "error");
    } finally {
      followupInFlightRef.current.delete(jobId);
    }
  }

  async function handleAcknowledgeQueueRequest(requestId: string) {
    setActionMessage("");
    setError("");
    try {
      const payload = await client.updateQueueRequestStatus(requestId, "acknowledged");
      setQueueRequests((current) => mergeQueueRequests(current, [payload.request]));
      await refreshPanels();
      setActionMessage("Queue packet acknowledged.");
      vibrateNotice(tg, "success");
    } catch (ackError) {
      setError(ackError instanceof Error ? ackError.message : "Queue packet could not be acknowledged.");
      vibrateNotice(tg, "error");
    }
  }

  async function handleSelectJob(jobId: string | null) {
    setSelectedJobId(jobId);
    setSelectedJobDetail(null);
    setError("");
    if (!jobId) return;
    setDetailLoading(true);
    try {
      const detail = await client.fetchJobDetail(jobId);
      setSelectedJobDetail(detail);
    } catch (detailError) {
      setError(detailError instanceof Error ? detailError.message : "Mission detail could not load.");
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => () => streamCleanupRef.current?.(), []);

  return (
    <MiniAppView
      appName={bootstrap?.appName || "ORION"}
      screen={screen}
      screenLabel={screenTitle(screen)}
      bridgeStatus={bridgeStatus}
      conversation={conversation}
      inbox={inbox}
      selectedJobDetail={selectedJobDetail}
      detailLoading={detailLoading}
      home={home}
      review={review}
      queueRequests={queueRequests}
      loading={loading}
      error={error}
      composerText={composerText}
      sending={sending}
      hasNativeMainButton={Boolean(tg?.MainButton)}
      actionMessage={actionMessage}
      selectedJobId={selectedJobId}
      onScreenChange={(next) => {
        goToRootScreen(next);
        vibrateSelection(tg);
      }}
      onComposerChange={setComposerText}
      onComposerSubmit={() => void handleSubmit()}
      onApproval={(approvalId, decision) => void handleApproval(approvalId, decision)}
      onTaskPacketApproval={(jobId, decision) => void handleTaskPacketApproval(jobId, decision)}
      onFollowup={(jobId) => void handleFollowup(jobId)}
      onAcknowledgeQueueRequest={(requestId) => void handleAcknowledgeQueueRequest(requestId)}
      onSelectJob={(jobId) => void handleSelectJob(jobId)}
      onQueueCenter={() => {
        openQueueCenter();
        vibrateSelection(tg);
      }}
    />
  );
}
