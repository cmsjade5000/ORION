import { useEffect, useMemo, useRef, useState } from "react";
import type {
  BootstrapPayload,
  ChatConversation,
  ChatRunPayload,
  HomePayload,
  InboxPayload,
  JobItem,
  MiniAppScreen,
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
  sendChat(input: { conversationId: string; message: string }): Promise<ChatRunPayload>;
  fetchRun(runId: string): Promise<ChatRunPayload>;
  streamRun(runId: string, onRun: (payload: ChatRunPayload) => void, onError: (message: string) => void): () => void;
  resolveApproval(approvalId: string, decision: "allow-once" | "allow-always" | "deny"): Promise<{ message: string; closesWebApp?: boolean }>;
  createFollowup(jobId: string): Promise<{ message: string }>;
};

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

export function createApiClient(): ApiClient {
  return {
    bootstrap: () => jsonFetch("/api/bootstrap"),
    home: () => jsonFetch("/api/home"),
    review: () => jsonFetch("/api/review"),
    inbox: () => jsonFetch("/api/inbox"),
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
    createFollowup: (jobId) =>
      jsonFetch(`/api/jobs/${encodeURIComponent(jobId)}/followup`, {
        method: "POST",
      }),
  };
}

type MiniAppViewProps = {
  appName: string;
  screen: MiniAppScreen;
  screenLabel: string;
  connectionPill: string;
  conversation: ChatConversation | null;
  inbox: InboxPayload | null;
  home: HomePayload | null;
  review: ReviewPayload | null;
  loading: boolean;
  error: string;
  composerText: string;
  sending: boolean;
  activityText: string;
  actionMessage: string;
  selectedJobId: string | null;
  onScreenChange(screen: MiniAppScreen): void;
  onComposerChange(text: string): void;
  onComposerSubmit(): void;
  onApproval(approvalId: string, decision: "allow-once" | "allow-always" | "deny"): void;
  onFollowup(jobId: string): void;
  onSelectJob(jobId: string | null): void;
};

export function MiniAppView(props: MiniAppViewProps) {
  const sections = props.inbox ? buildInboxSections(props.inbox) : [];
  const selectedJob =
    props.selectedJobId && props.inbox
      ? props.inbox.jobs.find((job) => job.job_id === props.selectedJobId) || null
      : null;

  return (
    <div className="starship-shell">
      <div className="starfield" aria-hidden="true" />
      <header className="hero">
        <div className="hero__eyebrow">Starship Console</div>
        <div className="hero__row">
          <div>
            <h1>{props.appName}</h1>
            <p className="hero__lede">A friendly bridge into ORION: chat up front, mission inbox on deck, today in view.</p>
          </div>
          <div className="signal-pill">{props.connectionPill}</div>
        </div>
      </header>

      <nav className="nav-grid" aria-label="ORION mini app sections">
        {(["chat", "inbox", "today"] as MiniAppScreen[]).map((screen) => (
          <button
            key={screen}
            type="button"
            className={`nav-chip ${props.screen === screen ? "is-active" : ""}`}
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
                <p className="panel__eyebrow">Primary Surface</p>
                <h2>{props.screenLabel}</h2>
              </div>
              <div className={`status-dot tone-${statusTone(props.sending ? "pending" : "complete")}`}>{props.activityText}</div>
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
              <button
                type="submit"
                className="button button--primary"
                disabled={props.sending || !props.conversation || !props.composerText.trim()}
              >
                {props.sending ? "Sending..." : "Send to ORION"}
              </button>
            </form>
          </section>
        ) : null}

        {props.screen === "inbox" ? (
          <section className="panel panel--inbox">
            <div className="panel__header">
              <div>
                <p className="panel__eyebrow">Actionable Queue</p>
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
                    props.inbox.jobs.map((job) => (
                      <article key={job.job_id} className={`list-card tone-${statusTone(job.state)}`}>
                        <div className="list-card__meta">
                          <span>{job.owner}</span>
                          <span>{job.state.replace(/_/g, " ")}</span>
                        </div>
                        <p>{job.objective}</p>
                        <div className="action-row">
                          <button type="button" className="button" onClick={() => props.onSelectJob(job.job_id)}>
                            Inspect
                          </button>
                          {isFollowupActionable(job) ? (
                            <button type="button" className="button button--primary" onClick={() => props.onFollowup(job.job_id)}>
                              Queue Follow-Up
                            </button>
                          ) : null}
                        </div>
                      </article>
                    ))
                  ) : (
                    <div className="empty-mini">Nothing is clogging the queue right now.</div>
                  )}
                </section>
              </div>

              <aside className="subpanel subpanel--detail">
                <h3>{selectedJob ? "Selected Work Item" : "Queue Notes"}</h3>
                {selectedJob ? (
                  <>
                    <p className="detail-title">{selectedJob.objective}</p>
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
                    <div className="action-row">
                      {isFollowupActionable(selectedJob) ? (
                        <button type="button" className="button button--primary" onClick={() => props.onFollowup(selectedJob.job_id)}>
                          Queue Follow-Up
                        </button>
                      ) : null}
                      <button type="button" className="button button--ghost" onClick={() => props.onSelectJob(null)}>
                        Close
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="empty-mini">
                    <p>Select a work item to inspect the packet context.</p>
                    <p>Approvals and follow-ups stay limited to existing command paths, not a shadow task system.</p>
                  </div>
                )}
              </aside>
            </div>
          </section>
        ) : null}

        {props.screen === "today" ? (
          <section className="panel panel--today">
            <div className="panel__header">
              <div>
                <p className="panel__eyebrow">Orientation</p>
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

export function MiniApp({ api = createApiClient() }: { api?: ApiClient }) {
  const tg = useMemo(() => getTelegramWebApp(), []);
  const [bootstrap, setBootstrap] = useState<BootstrapPayload | null>(null);
  const [conversation, setConversation] = useState<ChatConversation | null>(null);
  const [home, setHome] = useState<HomePayload | null>(null);
  const [review, setReview] = useState<ReviewPayload | null>(null);
  const [inbox, setInbox] = useState<InboxPayload | null>(null);
  const [screen, setScreen] = useState<MiniAppScreen>("chat");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [composerText, setComposerText] = useState("");
  const [sending, setSending] = useState(false);
  const [actionMessage, setActionMessage] = useState("");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [activityText, setActivityText] = useState("Bridge stable");
  const streamCleanupRef = useRef<(() => void) | null>(null);

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
    api
      .bootstrap()
      .then((bootstrapPayload) => {
        if (cancelled) return;
        setBootstrap(bootstrapPayload);
        setConversation(bootstrapPayload.conversation);
        setScreen(screenFromStartapp(bootstrapPayload.startapp));
        setError("");

        return Promise.allSettled([api.home(), api.review(), api.inbox()]).then((results) => {
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
  }, [api]);

  useEffect(() => {
    if (!tg?.MainButton || !tg?.BackButton) return;
    const mainButton = tg.MainButton;
    const backButton = tg.BackButton;
    const mainClick = () => {
      if (!sending) {
        void handleSubmit();
      }
    };
    const backClick = () => {
      if (screen === "inbox" && selectedJobId) {
        setSelectedJobId(null);
        return;
      }
        setScreen("chat");
    };

    mainButton.offClick(mainClick);
    backButton.offClick(backClick);
    mainButton.hide();
    backButton.hide();

    if (screen === "chat") {
      mainButton.setText(sending ? "Sending..." : "Send to ORION");
      if (composerText.trim() && conversation && !sending) {
        mainButton.enable?.();
      } else {
        mainButton.disable?.();
      }
      mainButton.show();
      mainButton.onClick(mainClick);
    }
    if (screen === "inbox" && selectedJobId) {
      backButton.show();
      backButton.onClick(backClick);
    }
    if (screen === "today") {
      backButton.show();
      backButton.onClick(backClick);
    }

    return () => {
      mainButton.offClick(mainClick);
      backButton.offClick(backClick);
    };
  }, [screen, selectedJobId, sending, tg, composerText]);

  function applyRun(run: ChatRunPayload) {
    setConversation(run.conversation);
    setActivityText(run.status === "completed" ? "Bridge stable" : run.status.replace(/_/g, " "));
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
    const [homePayload, reviewPayload, inboxPayload] = await Promise.all([api.home(), api.review(), api.inbox()]);
    setHome(homePayload);
    setReview(reviewPayload);
    setInbox(inboxPayload);
  }

  async function handleSubmit() {
    const text = composerText.trim();
    if (!text || sending || !conversation) return;
    setSending(true);
    setError("");
    setActionMessage("");
    setActivityText("Routing to ORION...");
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
      const run = await api.sendChat({
        conversationId: conversation.conversationId,
        message: text,
      });
      applyRun(run);
      streamCleanupRef.current?.();
      streamCleanupRef.current = api.streamRun(
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
      const payload = await api.resolveApproval(approvalId, decision);
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

  async function handleFollowup(jobId: string) {
    setActionMessage("");
    try {
      const payload = await api.createFollowup(jobId);
      setActionMessage(payload.message);
      await refreshPanels();
      vibrateNotice(tg, "success");
    } catch (followupError) {
      setError(followupError instanceof Error ? followupError.message : "Follow-up action failed.");
      vibrateNotice(tg, "error");
    }
  }

  useEffect(() => () => streamCleanupRef.current?.(), []);

  return (
    <MiniAppView
      appName={bootstrap?.appName || "ORION"}
      screen={screen}
      screenLabel={screenTitle(screen)}
      connectionPill={sending ? "Live link active" : "Bridge ready"}
      conversation={conversation}
      inbox={inbox}
      home={home}
      review={review}
      loading={loading}
      error={error}
      composerText={composerText}
      sending={sending}
      activityText={activityText}
      actionMessage={actionMessage}
      selectedJobId={selectedJobId}
      onScreenChange={(next) => {
        setScreen(next);
        setSelectedJobId(null);
        vibrateSelection(tg);
      }}
      onComposerChange={setComposerText}
      onComposerSubmit={() => void handleSubmit()}
      onApproval={(approvalId, decision) => void handleApproval(approvalId, decision)}
      onFollowup={(jobId) => void handleFollowup(jobId)}
      onSelectJob={setSelectedJobId}
    />
  );
}
