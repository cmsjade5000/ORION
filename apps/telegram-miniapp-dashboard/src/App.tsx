import { useEffect, useMemo, useRef, useState } from "react";
import NetworkDashboard from "./components/NetworkDashboard";
import CommandBar from "./components/CommandBar";
import { initTelegram } from "./telegram/init";
import { fetchLiveState, type LiveState } from "./api/state";
import { submitCommand } from "./api/command";
import { connectStateStream, getStreamToken, type StreamStatus } from "./api/events";
import FeedPanel from "./components/FeedPanel";
import FilesPanel from "./components/FilesPanel";
import WorkflowPanel from "./components/WorkflowPanel";
import OverlaySheet from "./components/OverlaySheet";
import AegisPanel from "./components/AegisPanel";

const DEFAULT_AGENTS = ["ATLAS", "EMBER", "PIXEL", "LEDGER", "AEGIS", "PULSE", "NODE", "STRATUS"] as const;

export default function App() {
  const [initData, setInitData] = useState<string>("");
  const [platform, setPlatform] = useState<string>("web");
  const [streamStatus, setStreamStatus] = useState<StreamStatus>("closed");
  const [polling, setPolling] = useState<boolean>(false);
  const [dlToken, setDlToken] = useState<string>("");
  const dlTokenExpiresAtRef = useRef<number>(0);
  const [authError, setAuthError] = useState<string>("");
  const [commandError, setCommandError] = useState<string>("");
  const [composerActive, setComposerActive] = useState<boolean>(false);
  const [orionFlareAt, setOrionFlareAt] = useState<number>(0);
  const [activeOverlay, setActiveOverlay] = useState<null | "activity" | "files" | "about" | "aegis">(null);
  const [activityTab, setActivityTab] = useState<"workflow" | "responses">("responses");
  const [activitySplit, setActivitySplit] = useState<boolean>(() => {
    try {
      return window.localStorage.getItem("orion.activitySplit") === "1";
    } catch {
      return false;
    }
  });
  const lastReadAtRef = useRef<number>(Date.now());
  const [hiddenOrbitArtifacts, setHiddenOrbitArtifacts] = useState<Set<string>>(() => new Set());
  const [deletedArtifacts, setDeletedArtifacts] = useState<Set<string>>(() => new Set());
  const tgRef = useRef<any>(null);
  const lastStateAtRef = useRef<number>(Date.now());
  const [state, setState] = useState<LiveState>({
    ts: Date.now(),
    activeAgentId: null,
    agents: DEFAULT_AGENTS.map((id) => ({ id, status: "idle" as const })),
  });

  // Telegram init: safe to run even when not inside Telegram.
  useEffect(() => {
    const tg = initTelegram();
    if (tg) {
      setAuthError("");
      setInitData(tg.initData);
      setPlatform(`${tg.platform} (tg v${tg.version})`);
      tgRef.current = tg.webApp as any;
    }
  }, []);

  // Load/store dismissed artifact ids locally (per-device).
  useEffect(() => {
    try {
      // Migration: old "dismissedArtifacts" meant "gone everywhere". Treat as deleted-from-view.
      const oldRaw = window.localStorage.getItem("orion.dismissedArtifacts");
      if (oldRaw) {
        const oldArr = JSON.parse(oldRaw);
        if (Array.isArray(oldArr)) {
          const next = new Set(oldArr.filter((x) => typeof x === "string").slice(0, 200));
          setDeletedArtifacts(next);
          window.localStorage.removeItem("orion.dismissedArtifacts");
          window.localStorage.setItem("orion.deletedArtifacts", JSON.stringify(Array.from(next)));
        }
      }

      const hiddenRaw = window.localStorage.getItem("orion.hiddenOrbitArtifacts") || "[]";
      const hiddenArr = JSON.parse(hiddenRaw);
      if (Array.isArray(hiddenArr)) setHiddenOrbitArtifacts(new Set(hiddenArr.filter((x) => typeof x === "string").slice(0, 400)));

      const deletedRaw = window.localStorage.getItem("orion.deletedArtifacts") || "[]";
      const deletedArr = JSON.parse(deletedRaw);
      if (Array.isArray(deletedArr)) setDeletedArtifacts(new Set(deletedArr.filter((x) => typeof x === "string").slice(0, 400)));
    } catch {
      // ignore
    }
  }, []);

  const hideOrbitArtifact = (id: string) => {
    if (!id) return;
    setHiddenOrbitArtifacts((prev) => {
      const next = new Set(prev);
      next.add(id);
      try {
        window.localStorage.setItem("orion.hiddenOrbitArtifacts", JSON.stringify(Array.from(next).slice(0, 400)));
      } catch {
        // ignore
      }
      return next;
    });
  };

  const unhideOrbitArtifact = (id: string) => {
    if (!id) return;
    setHiddenOrbitArtifacts((prev) => {
      if (!prev.has(id)) return prev;
      const next = new Set(prev);
      next.delete(id);
      try {
        window.localStorage.setItem("orion.hiddenOrbitArtifacts", JSON.stringify(Array.from(next).slice(0, 400)));
      } catch {
        // ignore
      }
      return next;
    });
  };

  const deleteArtifactFromView = (id: string) => {
    if (!id) return;
    setDeletedArtifacts((prev) => {
      const next = new Set(prev);
      next.add(id);
      try {
        window.localStorage.setItem("orion.deletedArtifacts", JSON.stringify(Array.from(next).slice(0, 400)));
      } catch {
        // ignore
      }
      return next;
    });
    // If it was hidden-in-orbit, remove that entry too (keeps state tidy).
    unhideOrbitArtifact(id);
  };

  const orionFeed = useMemo(() => {
    return (state.feed || []).filter((it) => it && it.kind === "response" && (it.agentId || "") === "ORION");
  }, [state.feed]);

  const aegisAgent = useMemo(() => {
    return (state.agents || []).find((a) => a && a.id === "AEGIS") || null;
  }, [state.agents]);

  const aegisFeed = useMemo(() => {
    const items = (state.feed || []).filter((it) => {
      if (!it) return false;
      const aid = String(it.agentId || "");
      if (aid === "AEGIS") return true;
      const text = String(it.text || "");
      return /(?:\bAEGIS\b|heartbeat|health|down|outage|no ack|noack|restarting)/i.test(text);
    });
    // newest first in the feed store already; keep a small cap
    return items.slice(0, 30);
  }, [state.feed]);

  const responsesOpen = activeOverlay === "activity" && (activitySplit || activityTab === "responses");

  // Mark feed read when opened (so notifications only show when something new arrives).
  useEffect(() => {
    if (!responsesOpen) return;
    const maxTs = Math.max(0, ...orionFeed.map((it) => (typeof it.ts === "number" ? it.ts : 0)));
    lastReadAtRef.current = Math.max(Date.now(), maxTs);
  }, [responsesOpen, orionFeed]);

  const unreadCount = useMemo(() => {
    if (responsesOpen) return 0;
    const since = lastReadAtRef.current || 0;
    return orionFeed.filter((it) => it && it.ts > since).length;
  }, [responsesOpen, orionFeed]);
  const stateForNetwork = useMemo(() => ({ ...state, feed: orionFeed }), [state, orionFeed]);

  // Keep a short-lived signed token refreshed for artifact downloads.
  // (Tokens expire; a stale token would make old artifact bubbles fail to download.)
  useEffect(() => {
    if (!initData) {
      dlTokenExpiresAtRef.current = 0;
      setDlToken("");
      return;
    }

    let cancelled = false;
    let t: number | null = null;

    const schedule = (expiresAt: number) => {
      if (t) window.clearTimeout(t);
      const now = Date.now();
      const refreshAt = Math.max(now + 30_000, expiresAt - 60_000); // refresh ~1m before expiry
      t = window.setTimeout(() => tick(), refreshAt - now);
    };

    const tick = async () => {
      try {
        const auth = await getStreamToken(initData);
        if (cancelled) return;
        dlTokenExpiresAtRef.current = auth.expiresAt;
        setDlToken(auth.token);
        schedule(auth.expiresAt);
      } catch (e) {
        // If token refresh fails, keep the last token; polling/SSE flows will surface auth errors.
        if (cancelled) return;
        schedule(Date.now() + 2 * 60_000); // retry soon
      }
    };

    tick();

    return () => {
      cancelled = true;
      if (t) window.clearTimeout(t);
    };
  }, [initData]);

  // Prefer push updates via SSE. If the stream isn't open, enable polling as a safety net.
  useEffect(() => {
    let cancelled = false;
    let conn: { close: () => void } | null = null;
    let retry = 0;
    let retryTimer: number | null = null;

    const backoffMs = (n: number) => {
      const base = Math.min(15_000, 600 * Math.pow(1.7, Math.min(10, n)));
      const jitter = Math.floor(Math.random() * 250);
      return Math.max(450, Math.floor(base + jitter));
    };

    const start = async () => {
      if (!initData) {
        setStreamStatus("closed");
        setPolling(false);
        return;
      }

      if (typeof EventSource === "undefined") {
        setPolling(true);
        setStreamStatus("closed");
        return;
      }

      // While connecting/reconnecting SSE, keep state fresh via polling.
      setPolling(true);
      setStreamStatus("connecting");

      try {
        const auth = await getStreamToken(initData);
        if (cancelled) return;

        conn = connectStateStream({
          token: auth.token,
          onState: (s) => {
            lastStateAtRef.current = Date.now();
            setState(s);
          },
          onStatus: (st) => {
            setStreamStatus(st);
            // When the stream is open, turn off polling. If it errors, polling will kick in.
            if (st === "open") {
              retry = 0;
              if (retryTimer) {
                window.clearTimeout(retryTimer);
                retryTimer = null;
              }
              setPolling(false);
              return;
            }
            if (st === "error") {
              retry += 1;
              setPolling(true);
              if (conn) conn.close();
              conn = null;
              const ms = backoffMs(retry);
              if (retryTimer) window.clearTimeout(retryTimer);
              retryTimer = window.setTimeout(() => start(), ms);
            }
          },
        });
      } catch (e) {
        retry += 1;
        setStreamStatus("error");
        setPolling(true);
        const msg = e instanceof Error ? e.message : String(e);
        // If server rejects initData, don't spin reconnect loops.
        if (msg.toLowerCase().includes("unauthorized")) {
          setAuthError(msg);
          setPolling(false);
          return;
        }
        const ms = backoffMs(retry);
        if (retryTimer) window.clearTimeout(retryTimer);
        retryTimer = window.setTimeout(() => start(), ms);
      }
    };

    start();
    return () => {
      cancelled = true;
      if (conn) conn.close();
      if (retryTimer) window.clearTimeout(retryTimer);
    };
  }, [initData]);

  useEffect(() => {
    if (!polling) return;
    if (!initData) return;
    if (authError) return;
    let cancelled = false;
    let intervalMs = 2000;
    let failures = 0;
    let timer: number | null = null;

    const tick = async () => {
      try {
        const next = await fetchLiveState({ initData });
        failures = 0;
        intervalMs = 2000;
        lastStateAtRef.current = Date.now();
        if (!cancelled) setState(next);
      } catch (e) {
        failures += 1;
        const msg = e instanceof Error ? e.message : String(e);
        if (msg.toLowerCase().includes("unauthorized") || msg.toLowerCase().includes("401")) {
          setAuthError(msg);
          setPolling(false);
          return;
        }
        // Back off on repeated failures.
        intervalMs = Math.min(15_000, Math.floor(2000 * Math.pow(1.7, Math.min(6, failures))));
      }

      if (cancelled) return;
      timer = window.setTimeout(() => tick(), intervalMs);
    };

    tick();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [polling, initData, authError]);

  const pill = useMemo(() => {
    if (!initData) return "No Telegram initData (running outside Telegram)";
    return `Telegram initData received (${initData.length} chars)`;
  }, [initData]);

  const netPill = useMemo(() => {
    if (polling) return "polling";
    return streamStatus;
  }, [polling, streamStatus]);

  return (
    <div className="appShell">
      <main className="card stage">
        <div className="stageInner">
          <NetworkDashboard
            state={stateForNetwork}
            token={dlToken}
            telegramWebApp={tgRef.current}
            composerActive={composerActive}
            orionFlareAt={orionFlareAt}
            onOpenFeed={() => {
              setActivityTab("responses");
              setActiveOverlay("activity");
            }}
            onOpenFiles={() => setActiveOverlay("files")}
            unreadCount={unreadCount}
            onOrionClick={() => setActiveOverlay(null)}
            hiddenOrbitArtifactIds={new Set([...hiddenOrbitArtifacts, ...deletedArtifacts])}
            onHideOrbitArtifact={hideOrbitArtifact}
          />
        </div>
        <div className="bottomBar" aria-label="Panels">
          <div className="bottomBarInner">
            <button
              type="button"
              className="bottomBarButton"
              onClick={() => {
                const wfRunning = Boolean(state.workflow && state.workflow.status === "running");
                setActivityTab(wfRunning ? "workflow" : "responses");
                setActiveOverlay("activity");
              }}
              title="Activity"
              aria-label="Activity"
            >
              🧭
              {unreadCount > 0 ? (
                <span className="edgeBadge" aria-label={`${unreadCount} new`}>
                  {unreadCount > 9 ? "9+" : String(unreadCount)}
                </span>
              ) : (state.workflow && state.workflow.status === "running") ? (
                <span className="edgeDot" aria-hidden="true" />
              ) : null}
            </button>

            <button
              type="button"
              className="bottomBarButton"
              onClick={() => setActiveOverlay("files")}
              title="Files"
              aria-label="Files"
            >
              📁
              {(state.artifacts || []).filter((a) => a && !deletedArtifacts.has(a.id)).length > 0 ? (
                <span className="edgeDot" aria-hidden="true" />
              ) : null}
            </button>

            <button
              type="button"
              className="bottomBarButton"
              onClick={() => setActiveOverlay("about")}
              title="Info"
              aria-label="Info"
            >
              ℹ️
            </button>

            <button
              type="button"
              className="bottomBarButton"
              onClick={() => setActiveOverlay("aegis")}
              title="AEGIS"
              aria-label="AEGIS"
            >
              <span className="aegisBottomIcon" aria-hidden="true">
                <span className="aegisBottomIconEmoji">🛰️</span>
                {(() => {
                  const a = aegisAgent;
                  if (!a) return <span className="edgeDot edgeDotWarn" aria-hidden="true" />;
                  const badge = String((a as any).badge || "");
                  const isAlarm = badge === "🚨" || a.status === "offline" || a.activity === "error";
                  const isWarn = !isAlarm && badge === "⚠️";
                  const cls = ["edgeDot", isAlarm ? "edgeDotAlarm" : isWarn ? "edgeDotWarn" : ""].filter(Boolean).join(" ");
                  return <span className={cls} aria-hidden="true" />;
                })()}
              </span>
            </button>
          </div>
        </div>
      </main>

      <footer className="card footerPanel footerPanelCompact">
        <div className="footerComposer">
          <CommandBar
            disabled={!initData || Boolean(authError)}
            placeholder={
              authError
                ? "Unauthorized (open from Telegram / configure initData verification)"
                : (initData ? "Ask ORION" : "Open via bot Web App button to enable commands")
            }
            onTypingChange={(t) => setComposerActive(Boolean(t))}
            onSubmit={async (text) => {
              setCommandError("");
              try {
                setOrionFlareAt(Date.now());
                // Light haptic on send, if available in this Telegram version.
                tgRef.current?.HapticFeedback?.impactOccurred?.("light");
                // Send to backend so ORION can later route this into task packets/sessions.
                const res = await submitCommand({ initData, text });
                // eslint-disable-next-line no-console
                console.log("command.accepted", res);
                return true;
              } catch (e) {
                const msg = e instanceof Error ? e.message : String(e);
                setCommandError(msg);
                return false;
              }
            }}
          />
          {authError ? (
            <div style={{ marginTop: 8, fontSize: 12, color: "#ffb4a2" }}>
              {authError}
            </div>
          ) : null}
          {commandError ? (
            <div style={{ marginTop: 8, fontSize: 12, color: "#ffb4a2" }}>
              {commandError}
            </div>
          ) : null}
        </div>
      </footer>

      <OverlaySheet
        open={activeOverlay === "activity"}
        title="Activity"
        subtitle={
          activitySplit
            ? "Workflow + Responses"
            : (activityTab === "workflow"
              ? "Workflow"
              : (unreadCount > 0 ? `${unreadCount} new` : "ORION only"))
        }
        onClose={() => setActiveOverlay(null)}
      >
        <div style={{ display: "grid", gap: 10 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                type="button"
                className={activitySplit ? "button buttonGhost" : (activityTab === "workflow" ? "button" : "button buttonGhost")}
                onClick={() => setActivityTab("workflow")}
                disabled={activitySplit}
                aria-label="Workflow tab"
              >
                🧭 Workflow
              </button>
              <button
                type="button"
                className={activitySplit ? "button buttonGhost" : (activityTab === "responses" ? "button" : "button buttonGhost")}
                onClick={() => setActivityTab("responses")}
                disabled={activitySplit}
                aria-label="Responses tab"
              >
                💬 Responses
              </button>
            </div>
            <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12, color: "rgba(255,255,255,0.72)" }}>
              <input
                type="checkbox"
                checked={activitySplit}
                onChange={(e) => {
                  const v = Boolean(e.target.checked);
                  setActivitySplit(v);
                  try {
                    window.localStorage.setItem("orion.activitySplit", v ? "1" : "0");
                  } catch {
                    // ignore
                  }
                }}
              />
              Split
            </label>
          </div>

          {activitySplit ? (
            <>
              <WorkflowPanel workflow={state.workflow || null} open={true} onToggle={() => null} variant="overlay" />
              <FeedPanel items={orionFeed} open={true} onToggle={() => null} unreadCount={0} variant="overlay" maxItems={30} />
            </>
          ) : activityTab === "workflow" ? (
            <WorkflowPanel workflow={state.workflow || null} open={true} onToggle={() => null} variant="overlay" />
          ) : (
            <FeedPanel items={orionFeed} open={true} onToggle={() => null} unreadCount={0} variant="overlay" maxItems={30} />
          )}
        </div>
      </OverlaySheet>

      <OverlaySheet
        open={activeOverlay === "files"}
        title="Files"
        subtitle={`${(state.artifacts || []).filter((a) => a && !deletedArtifacts.has(a.id)).length} available`}
        onClose={() => setActiveOverlay(null)}
      >
        <FilesPanel
          artifacts={(state.artifacts || []).filter((a) => a && !deletedArtifacts.has(a.id))}
          open={true}
          onToggle={() => null}
          token={dlToken}
          telegramWebApp={tgRef.current}
          hiddenOrbitIds={hiddenOrbitArtifacts}
          onUnhideOrbit={unhideOrbitArtifact}
          onDeleteFromView={deleteArtifactFromView}
          variant="overlay"
        />
      </OverlaySheet>

      <OverlaySheet
        open={activeOverlay === "about"}
        title="Info"
        subtitle="Mini app status"
        onClose={() => setActiveOverlay(null)}
      >
        <div style={{ display: "grid", gap: 10 }}>
          <div className="pill">{platform}</div>
          <div className="pill">connection: {netPill}</div>
          <div className="pill">{pill}</div>
        </div>
      </OverlaySheet>

      <OverlaySheet
        open={activeOverlay === "aegis"}
        title="AEGIS"
        subtitle="Health"
        onClose={() => setActiveOverlay(null)}
      >
        <AegisPanel aegis={aegisAgent} items={aegisFeed} />
      </OverlaySheet>
    </div>
  );
}
