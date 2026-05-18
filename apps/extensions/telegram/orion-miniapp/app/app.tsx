import { useEffect, useMemo, useState, type ReactNode } from "react";
import type {
  ActionDescriptor,
  ActionPreview,
  ActionRun,
  ActivityItem,
  AuditEvent,
  BootstrapPayload,
  ChatConversation,
  ChatRunPayload,
  CleanupCandidate,
  ControlDeckSnapshot,
  ControlDeckTone,
  HealthSignal,
  HomePayload,
  InboxPayload,
  JobDetailPayload,
  LaunchAgentSignal,
  MiniAppScreen,
  QueueRequest,
  QueueRequestStatus,
  RepoSignal,
  ReviewPayload,
} from "./types";
import {
  applySafeAreaInsets,
  applyTelegramTheme,
  getTelegramWebApp,
  prepareTelegramShell,
  vibrateNotice,
  vibrateSelection,
} from "./telegram";
import { buildActivityFeed, buildTaskRows, formatRelativeTime, screenFromStartapp, screenTitle } from "./view-model";

type QueueRequestView = Omit<QueueRequest, "status"> & {
  status: QueueRequestStatus | "queuing";
};

type RouteEntry = {
  screen: MiniAppScreen;
  taskId?: string;
};

type ControlAction = {
  actionId?: string;
  candidateIds?: string[];
  confirm?: string;
  detail?: string;
  itemId?: string;
};

type ApiClient = {
  bootstrap(): Promise<BootstrapPayload>;
  home(): Promise<HomePayload>;
  review(): Promise<ReviewPayload>;
  inbox(): Promise<InboxPayload>;
  controlDeckSnapshot(): Promise<ControlDeckSnapshot>;
  controlDeckActions(): Promise<{ actions: ActionDescriptor[] }>;
  controlDeckAudit(): Promise<{ events: AuditEvent[] }>;
  previewControlDeckAction(actionId: string, input?: ControlAction): Promise<ActionPreview>;
  approveControlDeckAction(actionId: string, input?: ControlAction): Promise<ActionRun>;
  restoreControlDeckAction(actionId: string, input?: ControlAction): Promise<ActionRun>;
  fetchJobDetail(jobId: string): Promise<JobDetailPayload>;
  sendChat(input: { conversationId: string; message: string }): Promise<ChatRunPayload>;
  resolveApproval(approvalId: string, decision: "allow-once" | "allow-always" | "deny"): Promise<{ message: string; closesWebApp?: boolean }>;
  resolveTaskPacketApproval(jobId: string, decision: "approve-once" | "deny"): Promise<{ message: string; duplicate?: boolean }>;
  createFollowup(jobId: string): Promise<{ message: string; request?: QueueRequest; duplicate?: boolean }>;
  updateQueueRequestStatus(requestId: string, status: QueueRequestStatus): Promise<{ request: QueueRequest }>;
};

const NAV: MiniAppScreen[] = ["deck", "compose", "queue", "status", "activity", "settings"];

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
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (tg?.initData) headers["X-Telegram-Init-Data"] = tg.initData;
  return fetch(withInitData(url), {
    ...options,
    headers: { ...headers, ...(options?.headers || {}) },
  }).then(async (response) => {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(String((payload as { error?: string }).error || `Request failed: ${response.status}`));
    return payload as T;
  });
}

export function createApiClient(): ApiClient {
  return {
    bootstrap: () => jsonFetch("/api/bootstrap"),
    home: () => jsonFetch("/api/home"),
    review: () => jsonFetch("/api/review"),
    inbox: () => jsonFetch("/api/inbox"),
    controlDeckSnapshot: () => jsonFetch("/api/control-deck/snapshot"),
    controlDeckActions: () => jsonFetch("/api/control-deck/actions"),
    controlDeckAudit: () => jsonFetch("/api/control-deck/audit"),
    previewControlDeckAction: (actionId, input) =>
      jsonFetch(`/api/control-deck/actions/${encodeURIComponent(actionId)}/preview`, {
        method: "POST",
        body: JSON.stringify(input ?? { actionId }),
      }),
    approveControlDeckAction: (actionId, input) =>
      jsonFetch(`/api/control-deck/actions/${encodeURIComponent(actionId)}/approve`, {
        method: "POST",
        body: JSON.stringify(input ?? { actionId }),
      }),
    restoreControlDeckAction: (actionId, input) =>
      jsonFetch(`/api/control-deck/quarantine/${encodeURIComponent(String(input?.itemId || actionId))}/restore`, {
        method: "POST",
        body: JSON.stringify({ confirm: "RESTORE", ...(input ?? { actionId }) }),
      }),
    fetchJobDetail: (jobId) => jsonFetch(`/api/inbox/jobs/${encodeURIComponent(jobId)}`),
    sendChat: (input) => jsonFetch("/api/chat/runs", { method: "POST", body: JSON.stringify(input) }),
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
    createFollowup: (jobId) => jsonFetch(`/api/jobs/${encodeURIComponent(jobId)}/followup`, { method: "POST" }),
    updateQueueRequestStatus: (requestId, status) =>
      jsonFetch(`/api/queue-requests/${encodeURIComponent(requestId)}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
  };
}

function toneClass(tone?: ControlDeckTone) {
  return `tone-${tone || "neutral"}`;
}

function prettyBytes(value?: number | null) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = bytes;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size >= 10 || index === 0 ? size.toFixed(0) : size.toFixed(1)} ${units[index]}`;
}

function publicUiError(error: unknown, fallback: string) {
  const message = error instanceof Error ? error.message : String(error || "");
  if (/token|secret|key|credential|authorization|bearer/i.test(message)) return fallback;
  return message || fallback;
}

function Panel({ title, subtitle, children, className = "" }: { title: string; subtitle?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`deck-panel ${className}`}>
      <header className="deck-panel__header">
        <div>
          <h2>{title}</h2>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      </header>
      {children}
    </section>
  );
}

function SignalRow({ signal }: { signal: HealthSignal }) {
  return (
    <article className="signal-row">
      <span className={`signal-dot ${toneClass(signal.tone)}`} />
      <div>
        <h3>{signal.label}</h3>
        <p>{signal.detail || signal.status}</p>
      </div>
      <strong className={toneClass(signal.tone)}>{signal.status}</strong>
    </article>
  );
}

function RepoRow({ repo }: { repo: RepoSignal }) {
  return (
    <article className="signal-row">
      <span className={`signal-dot ${toneClass(repo.tone)}`} />
      <div>
        <h3>{repo.name}</h3>
        <p>{repo.branch || "no branch"} · {repo.path}</p>
      </div>
      <strong className={toneClass(repo.tone)}>{repo.status}</strong>
    </article>
  );
}

function LaunchAgentRow({ agent }: { agent: LaunchAgentSignal }) {
  return (
    <article className="signal-row signal-row--compact">
      <span className={`signal-dot ${toneClass(agent.tone)}`} />
      <div>
        <h3>{agent.label}</h3>
        <p>{agent.detail || "launchd"}</p>
      </div>
      <strong className={toneClass(agent.tone)}>{agent.lastExitStatus ?? agent.status}</strong>
    </article>
  );
}

function ActivityRows({ events, fallback }: { events: AuditEvent[]; fallback: ActivityItem[] }) {
  const rows = events.length
    ? events.map((event) => ({
        id: event.id,
        title: event.title,
        detail: event.detail || event.type,
        at: event.at,
        tone: event.status === "failed" || event.status === "blocked" ? "warn" : "good",
      }))
    : fallback.slice(0, 10).map((item) => ({
        id: item.id,
        title: item.title,
        detail: item.detail,
        at: new Date(item.atMs).toISOString(),
        tone: item.type === "approval" ? "warn" : "neutral",
      }));
  return (
    <div className="activity-stack">
      {rows.length ? (
        rows.map((row) => (
          <article key={row.id} className="activity-card">
            <p className={toneClass(row.tone as ControlDeckTone)}>{row.title}</p>
            <span>{row.detail}</span>
            <small>{Number.isFinite(Date.parse(row.at)) ? formatRelativeTime(Date.now() - Date.parse(row.at)) : "recent"}</small>
          </article>
        ))
      ) : (
        <p className="empty-mini">No activity yet.</p>
      )}
    </div>
  );
}

function CleanupPanel({
  candidates,
  selected,
  busy,
  preview,
  run,
  onToggle,
  onPreview,
  onQuarantine,
  onRestore,
}: {
  candidates: CleanupCandidate[];
  selected: Set<string>;
  busy: boolean;
  preview: ActionPreview | null;
  run: ActionRun | null;
  onToggle(id: string): void;
  onPreview(): void;
  onQuarantine(): void;
  onRestore(): void;
}) {
  const selectedCount = selected.size;
  return (
    <Panel title="Cleanup" subtitle="Preview first. Quarantine only. No permanent deletion in v1.">
      <div className="cleanup-list">
        {candidates.length ? (
          candidates.map((candidate) => (
            <label key={candidate.id} className="cleanup-item">
              <input type="checkbox" checked={selected.has(candidate.id)} onChange={() => onToggle(candidate.id)} />
              <span>
                <strong>{candidate.label}</strong>
                <small>{candidate.description}</small>
              </span>
              <b>{prettyBytes(candidate.sizeBytes)}</b>
            </label>
          ))
        ) : (
          <p className="empty-mini">No cleanup candidates found.</p>
        )}
      </div>
      <div className="deck-actions">
        <button type="button" className="button" onClick={onPreview} disabled={busy || !selectedCount}>
          Preview Selected
        </button>
        <button type="button" className="button button--primary" onClick={onQuarantine} disabled={busy || !selectedCount}>
          Quarantine Selected
        </button>
        {run?.restoreToken ? (
          <button type="button" className="button button--ghost" onClick={onRestore} disabled={busy}>
            Restore Last Run
          </button>
        ) : null}
      </div>
      {preview ? (
        <div className="action-result">
          <strong>{preview.title}</strong>
          <p>{preview.summary}</p>
          {(preview.changes || []).map((change) => <span key={change}>{change}</span>)}
        </div>
      ) : null}
      {run ? (
        <div className={`action-result action-result--${run.status}`}>
          <strong>{run.message}</strong>
          {(run.output || []).slice(0, 4).map((line) => <span key={line}>{line}</span>)}
        </div>
      ) : null}
    </Panel>
  );
}

function ControlDeckScreen({
  snapshot,
  actions,
  busy,
  preview,
  run,
  selectedCleanup,
  onRefresh,
  onAcknowledge,
  onToggleCleanup,
  onPreviewCleanup,
  onQuarantineCleanup,
  onRestoreCleanup,
  onPreviewAction,
  onNavigate,
}: {
  snapshot: ControlDeckSnapshot | null;
  actions: ActionDescriptor[];
  busy: boolean;
  preview: ActionPreview | null;
  run: ActionRun | null;
  selectedCleanup: Set<string>;
  onRefresh(): void;
  onAcknowledge(signal: HealthSignal): void;
  onToggleCleanup(id: string): void;
  onPreviewCleanup(): void;
  onQuarantineCleanup(): void;
  onRestoreCleanup(): void;
  onPreviewAction(action: ActionDescriptor): void;
  onNavigate(screen: MiniAppScreen): void;
}) {
  if (!snapshot) {
    return (
      <main className="deck-grid">
        <Panel title="Mac Mini Control Deck">
          <p className="empty-mini">Loading workstation state...</p>
        </Panel>
      </main>
    );
  }
  const primaryActions = actions.filter((action) => action.enabled !== false).slice(0, 4);
  return (
    <main className="deck-grid">
      <section className={`verdict-card ${toneClass(snapshot.verdict.tone)}`}>
        <div>
          <p className="deck-kicker">Mac Mini Control Deck</p>
          <h1>{snapshot.verdict.title}</h1>
          <p>{snapshot.verdict.summary}</p>
        </div>
        <div className="verdict-actions">
          <button type="button" className="button button--primary" onClick={onRefresh} disabled={busy}>
            Refresh
          </button>
          <button type="button" className="button" onClick={() => onNavigate("compose")}>
            Ask ORION
          </button>
        </div>
      </section>

      <Panel title="Attention" subtitle="Only items that deserve a look.">
        <div className="signal-stack">
          {snapshot.attentionItems.length ? (
            snapshot.attentionItems.slice(0, 8).map((item) => (
              <article key={item.id} className="signal-row">
                <span className={`signal-dot ${toneClass(item.tone)}`} />
                <div>
                  <h3>{item.label}</h3>
                  <p>{item.detail || item.nextStep || item.status}</p>
                </div>
                <button type="button" className="button button--ghost" onClick={() => onAcknowledge(item)} disabled={busy}>
                  Ack
                </button>
              </article>
            ))
          ) : (
            <p className="empty-mini">No attention items.</p>
          )}
        </div>
      </Panel>

      <Panel title="Quick Actions" subtitle="Allowlisted actions only.">
        <div className="deck-actions">
          {primaryActions.map((action) => (
            <button
              key={action.id}
              type="button"
              className="button"
              disabled={!action.enabled || busy}
              onClick={() => onPreviewAction(action)}
            >
              {action.title}
            </button>
          ))}
        </div>
      </Panel>

      <Panel title="ORION" subtitle="Gateway, follow-through, and runtime posture.">
        <div className="signal-stack">{snapshot.orion.map((item) => <SignalRow key={item.id} signal={item} />)}</div>
      </Panel>

      <Panel title="Workstation" subtitle="Disk, tools, backup, and hot process signals.">
        <div className="signal-stack">{snapshot.workstation.map((item) => <SignalRow key={item.id} signal={item} />)}</div>
      </Panel>

      <Panel title="Repos" subtitle="Active local project drift under ~/src.">
        <div className="signal-stack">{snapshot.repos.slice(0, 8).map((repo) => <RepoRow key={repo.id} repo={repo} />)}</div>
      </Panel>

      <Panel title="LaunchAgents" subtitle="Generic service health, including market jobs as launchd signals only.">
        <div className="signal-stack">{snapshot.launchAgents.slice(0, 10).map((agent) => <LaunchAgentRow key={agent.id} agent={agent} />)}</div>
      </Panel>

      <CleanupPanel
        candidates={snapshot.cleanup}
        selected={selectedCleanup}
        busy={busy}
        preview={preview}
        run={run}
        onToggle={onToggleCleanup}
        onPreview={onPreviewCleanup}
        onQuarantine={onQuarantineCleanup}
        onRestore={onRestoreCleanup}
      />

      <Panel title="Activity" subtitle="Control Deck audit trail and recent ORION events.">
        <ActivityRows events={snapshot.activity} fallback={[]} />
      </Panel>
    </main>
  );
}

function ComposeScreen({
  text,
  sending,
  onChange,
  onSubmit,
}: {
  text: string;
  sending: boolean;
  onChange(value: string): void;
  onSubmit(): void;
}) {
  return (
    <main className="deck-grid deck-grid--single">
      <Panel title="Ask ORION" subtitle="One clear request. The response stays on the ORION runtime path.">
        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          <textarea value={text} onChange={(event) => onChange(event.target.value)} placeholder="Tell ORION exactly what to do next..." />
          <button type="submit" className="button button--primary" disabled={sending || !text.trim()}>
            {sending ? "Sending..." : "Send"}
          </button>
        </form>
      </Panel>
    </main>
  );
}

function QueueScreen({ inbox, onFollowup }: { inbox: InboxPayload | null; onFollowup(jobId: string): void }) {
  const tasks = buildTaskRows(inbox);
  return (
    <main className="deck-grid deck-grid--single">
      <Panel title="ORION Queue" subtitle="Delegated work and packets from tasks/JOBS/summary.json.">
        <div className="signal-stack">
          {tasks.length ? (
            tasks.map((task) => (
              <article key={task.id} className="signal-row">
                <span className={`signal-dot ${task.status === "failed" ? "tone-alert" : task.status === "needs_input" ? "tone-warn" : "tone-good"}`} />
                <div>
                  <h3>{task.objective}</h3>
                  <p>{task.owner} · {task.id}</p>
                </div>
                <button type="button" className="button" onClick={() => onFollowup(task.id)}>
                  Follow Up
                </button>
              </article>
            ))
          ) : (
            <p className="empty-mini">No delegated work in the queue.</p>
          )}
        </div>
      </Panel>
    </main>
  );
}

function StatusScreen({ snapshot }: { snapshot: ControlDeckSnapshot | null }) {
  return (
    <main className="deck-grid">
      <Panel title="System Status" subtitle="All read-only signals currently powering the deck.">
        <div className="signal-stack">
          {[...(snapshot?.workstation || []), ...(snapshot?.orion || [])].map((item) => <SignalRow key={item.id} signal={item} />)}
        </div>
      </Panel>
    </main>
  );
}

function SettingsScreen({ bootstrap }: { bootstrap: BootstrapPayload | null }) {
  return (
    <main className="deck-grid deck-grid--single">
      <Panel title="Settings" subtitle="Access and shell diagnostics.">
        <dl className="settings-grid">
          <div><dt>App</dt><dd>{bootstrap?.appName || "Mac Mini Control Deck"}</dd></div>
          <div><dt>Auth</dt><dd>{(bootstrap as BootstrapPayload & { authType?: string } | null)?.authType || "telegram/local"}</dd></div>
          <div><dt>Operator IDs</dt><dd>{bootstrap?.operatorIdsConfigured ? "configured" : "missing"}</dd></div>
          <div><dt>User</dt><dd>{bootstrap?.user?.first_name || bootstrap?.user?.username || "local"}</dd></div>
        </dl>
      </Panel>
    </main>
  );
}

function Shell({
  route,
  loading,
  error,
  message,
  children,
  onNavigate,
}: {
  route: MiniAppScreen;
  loading: boolean;
  error: string;
  message: string;
  children: ReactNode;
  onNavigate(screen: MiniAppScreen): void;
}) {
  return (
    <div className="orion-shell control-deck-shell">
      <header className="deck-topbar">
        <div>
          <p className="deck-kicker">ORION Relay Console</p>
          <h1>Mac Mini Control Deck</h1>
        </div>
        <span className={`bridge-status ${loading ? "tone-warn" : error ? "tone-alert" : "tone-good"}`}>
          {loading ? "Syncing" : error ? "Needs attention" : "Online"}
        </span>
      </header>
      <nav className="chip-nav" aria-label="Primary routes">
        {NAV.map((screen) => (
          <button
            key={screen}
            type="button"
            className={`chip-nav__btn ${route === screen ? "is-active" : ""}`}
            onClick={() => {
              vibrateSelection(getTelegramWebApp());
              onNavigate(screen);
            }}
          >
            {screenTitle(screen)}
          </button>
        ))}
      </nav>
      {error ? <p className="banner banner--error">{error}</p> : null}
      {message ? <p className="banner banner--info">{message}</p> : null}
      {children}
    </div>
  );
}

export function MiniApp({ api: providedApi }: { api?: ApiClient }) {
  const client = useMemo(() => providedApi ?? createApiClient(), [providedApi]);
  const tg = useMemo(() => getTelegramWebApp(), []);
  const [bootstrap, setBootstrap] = useState<BootstrapPayload | null>(null);
  const [conversation, setConversation] = useState<ChatConversation | null>(null);
  const [home, setHome] = useState<HomePayload | null>(null);
  const [review, setReview] = useState<ReviewPayload | null>(null);
  const [inbox, setInbox] = useState<InboxPayload | null>(null);
  const [snapshot, setSnapshot] = useState<ControlDeckSnapshot | null>(null);
  const [actions, setActions] = useState<ActionDescriptor[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [route, setRoute] = useState<RouteEntry>({ screen: "deck" });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [composerText, setComposerText] = useState("");
  const [sending, setSending] = useState(false);
  const [selectedCleanup, setSelectedCleanup] = useState<Set<string>>(new Set());
  const [preview, setPreview] = useState<ActionPreview | null>(null);
  const [run, setRun] = useState<ActionRun | null>(null);

  const activity = useMemo(() => buildActivityFeed(home, inbox, inbox?.queueRequests || [], review), [home, inbox, review]);
  const mergedSnapshot = useMemo(() => (snapshot ? { ...snapshot, activity: audit.length ? audit : snapshot.activity } : null), [snapshot, audit]);

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

  async function refreshAll() {
    const [bootstrapPayload, homePayload, reviewPayload, inboxPayload, deckPayload, actionPayload, auditPayload] = await Promise.all([
      client.bootstrap(),
      client.home(),
      client.review(),
      client.inbox(),
      client.controlDeckSnapshot(),
      client.controlDeckActions(),
      client.controlDeckAudit(),
    ]);
    setBootstrap(bootstrapPayload);
    setConversation(bootstrapPayload.conversation);
    setHome(homePayload);
    setReview(reviewPayload);
    setInbox(inboxPayload);
    setSnapshot(deckPayload);
    setActions(actionPayload.actions || []);
    setAudit(auditPayload.events || []);
    const start = screenFromStartapp(bootstrapPayload.startapp);
    setRoute({ screen: start === "home" ? "deck" : start });
  }

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    refreshAll()
      .then(() => {
        if (!cancelled) setError("");
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Control Deck could not load.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  async function runDeckAction(input: ControlAction) {
    if (!input.actionId) {
      setError("Action failed.");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await client.approveControlDeckAction(input.actionId, input);
      setRun(result);
      if (result.status === "succeeded") {
        setMessage(result.message);
        vibrateNotice(tg, "success");
        await refreshAll();
      } else {
        setError(result.message || "Action did not complete.");
        vibrateNotice(tg, "error");
      }
    } catch (err) {
      setError(publicUiError(err, "Action failed."));
      vibrateNotice(tg, "error");
    } finally {
      setBusy(false);
    }
  }

  async function handlePreviewCleanup() {
    setBusy(true);
    setPreview(null);
    setRun(null);
    try {
      const payload = await client.previewControlDeckAction("preview-cleanup", {
        actionId: "preview-cleanup",
        candidateIds: [...selectedCleanup],
      });
      setPreview(payload);
    } catch (err) {
      setError(publicUiError(err, "Cleanup preview failed."));
    } finally {
      setBusy(false);
    }
  }

  async function previewDeckAction(action: ActionDescriptor) {
    setBusy(true);
    setPreview(null);
    setRun(null);
    setError("");
    setMessage("");
    try {
      const payload = await client.previewControlDeckAction(action.id, { actionId: action.id });
      setPreview(payload);
      setMessage(payload.summary);
      vibrateSelection(tg);
    } catch (err) {
      setError(publicUiError(err, "Action preview failed."));
      vibrateNotice(tg, "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleRestoreCleanup() {
    if (!run?.restoreToken) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await client.restoreControlDeckAction("quarantine-cleanup", {
        actionId: "quarantine-cleanup",
        itemId: run.restoreToken,
        detail: run.restoreToken,
      });
      setRun(result);
      if (result.status === "succeeded") {
        setMessage(result.message);
        vibrateNotice(tg, "success");
        await refreshAll();
      } else {
        setError(result.message || "Restore did not complete.");
        vibrateNotice(tg, "error");
      }
    } catch (err) {
      setError(publicUiError(err, "Restore failed."));
      vibrateNotice(tg, "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmit() {
    const text = composerText.trim();
    if (!text || !conversation) return;
    setSending(true);
    setError("");
    try {
      const runPayload = await client.sendChat({ conversationId: conversation.conversationId, message: text });
      setConversation(runPayload.conversation);
      setComposerText("");
      setMessage(runPayload.lastMessage || "Request sent to ORION.");
      await refreshAll();
      vibrateNotice(tg, "success");
    } catch (err) {
      setError(publicUiError(err, "ORION did not accept this request."));
      vibrateNotice(tg, "error");
    } finally {
      setSending(false);
    }
  }

  function handleToggleCleanup(id: string) {
    setSelectedCleanup((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <Shell route={route.screen} loading={loading} error={error} message={message} onNavigate={(screen) => setRoute({ screen })}>
      {route.screen === "deck" || route.screen === "home" ? (
        <ControlDeckScreen
          snapshot={mergedSnapshot}
          actions={actions}
          busy={busy}
          preview={preview}
          run={run}
          selectedCleanup={selectedCleanup}
          onRefresh={() => {
            setBusy(true);
            refreshAll()
              .then(() => setMessage("Control Deck refreshed."))
              .catch((err) => setError(publicUiError(err, "Refresh failed.")))
              .finally(() => setBusy(false));
          }}
          onAcknowledge={(item) => runDeckAction({ actionId: "acknowledge-issue", detail: `${item.label}: ${item.status}` })}
          onToggleCleanup={handleToggleCleanup}
          onPreviewCleanup={handlePreviewCleanup}
          onQuarantineCleanup={() =>
            runDeckAction({
              actionId: "quarantine-cleanup",
              candidateIds: [...selectedCleanup],
              confirm: "QUARANTINE",
            })
          }
          onRestoreCleanup={handleRestoreCleanup}
          onPreviewAction={previewDeckAction}
          onNavigate={(screen) => setRoute({ screen })}
        />
      ) : null}

      {route.screen === "compose" ? (
        <ComposeScreen text={composerText} sending={sending} onChange={setComposerText} onSubmit={handleSubmit} />
      ) : null}

      {route.screen === "queue" ? (
        <QueueScreen
          inbox={inbox}
          onFollowup={(jobId) => {
            client
              .createFollowup(jobId)
              .then((payload) => {
                setMessage(payload.message);
                return refreshAll();
              })
              .catch((err) => setError(publicUiError(err, "Follow-up failed.")));
          }}
        />
      ) : null}

      {route.screen === "status" ? <StatusScreen snapshot={mergedSnapshot} /> : null}

      {route.screen === "activity" ? (
        <main className="deck-grid deck-grid--single">
          <Panel title="Activity" subtitle="Audit trail and runtime events.">
            <ActivityRows events={mergedSnapshot?.activity || []} fallback={activity} />
          </Panel>
        </main>
      ) : null}

      {route.screen === "settings" ? <SettingsScreen bootstrap={bootstrap} /> : null}
    </Shell>
  );
}

export function MiniAppView(props: Record<string, any>) {
  const route = props.route || { screen: "deck" };
  const tasks = Array.isArray(props.tasks) ? props.tasks : [];
  if (route.screen === "compose") {
    return (
      <div className="orion-shell">
        <ChipShim active="compose" onNavigate={props.onNavigate} />
        <h2>Compose Request</h2>
        <textarea value={props.composerText || ""} onChange={(event) => props.onComposerChange?.(event.target.value)} />
        <button type="button" className="button button--primary" disabled={props.sending} onClick={() => props.onComposerSubmit?.()}>
          Send to ORION
        </button>
      </div>
    );
  }
  if (route.screen === "queue") {
    return (
      <div className="orion-shell">
        <ChipShim active="queue" onNavigate={props.onNavigate} />
        {tasks.length ? (
          tasks.map((task: { id: string; objective: string }) => (
            <article key={task.id} className="task-row">
              <p>{task.objective}</p>
              <button type="button" className="button" onClick={() => props.onOpenTask?.(task.id)}>Open Task</button>
            </article>
          ))
        ) : (
          <p>No tasks match this filter.</p>
        )}
      </div>
    );
  }
  if (route.screen === "task") {
    const detail = props.selectedJobDetail;
    return (
      <div className="orion-shell">
        <h2>Task Detail</h2>
        {detail?.needSummary ? <p>{detail.needSummary}</p> : null}
        <button type="button" className="button" onClick={() => props.onTaskPacketApproval?.(route.taskId || detail?.job?.job_id, "approve-once")}>Approve Once</button>
        <button type="button" className="button" onClick={() => props.onApproval?.("abc", "allow-once")}>Allow Once</button>
        <button type="button" className="button" onClick={() => props.onAcknowledgeQueueRequest?.("qr-1")}>Acknowledge Packet</button>
      </div>
    );
  }
  return (
    <div className="orion-shell">
      <ChipShim active={route.screen} onNavigate={props.onNavigate} />
      <h2>What is Orion doing right now?</h2>
      <h2>Daily loop</h2>
      <button type="button" className="button" onClick={() => props.onNavigate?.("compose")}>New Request</button>
      <button type="button" className="button" onClick={() => props.onComposerChange?.("/followups")}>What needs me?</button>
      <button type="button" className="button" onClick={() => props.onComposerChange?.("/today")}>Plan today</button>
      <h2>System Health</h2>
    </div>
  );
}

function ChipShim({ active, onNavigate }: { active: MiniAppScreen; onNavigate?: (screen: MiniAppScreen) => void }) {
  return (
    <nav className="chip-nav" aria-label="Primary routes">
      {["deck", "home", "compose", "queue", "status", "activity", "settings"].map((screen) => (
        <button
          key={screen}
          type="button"
          className={`chip-nav__btn ${active === screen ? "is-active" : ""}`}
          onClick={() => onNavigate?.(screen as MiniAppScreen)}
        >
          {screenTitle(screen as MiniAppScreen)}
        </button>
      ))}
    </nav>
  );
}

export { ControlDeckScreen };
