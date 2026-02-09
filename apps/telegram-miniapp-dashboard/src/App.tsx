import { useEffect, useMemo, useRef, useState } from "react";
import NetworkDashboard from "./components/NetworkDashboard";
import CommandBar from "./components/CommandBar";
import { initTelegram } from "./telegram/init";
import { fetchLiveState, type LiveState } from "./api/state";
import { submitCommand } from "./api/command";
import { connectStateStream, getStreamToken, type StreamStatus } from "./api/events";

const DEFAULT_AGENTS = ["ATLAS", "EMBER", "PIXEL", "AEGIS", "LEDGER"] as const;

export default function App() {
  const [initData, setInitData] = useState<string>("");
  const [platform, setPlatform] = useState<string>("web");
  const [streamStatus, setStreamStatus] = useState<StreamStatus>("closed");
  const [polling, setPolling] = useState<boolean>(false);
  const [authError, setAuthError] = useState<string>("");
  const [commandError, setCommandError] = useState<string>("");
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
      <header className="topBar">
        <div className="topBarTitle">ORION NETWORK</div>
        <div className="pill">{platform} · {netPill}</div>
      </header>

      <main className="card stage">
        <div className="stageInner">
          <NetworkDashboard state={state} />
        </div>
        <div className="legend">
          <span>
            <span className="dot dotOk" /> active
          </span>
          <span>
            <span className="dot dotWarn" /> busy
          </span>
          <span>
            <span className="dot dotOff" /> idle/off
          </span>
          <span style={{ marginLeft: "auto" }}>{pill}</span>
        </div>
      </main>

      <footer className="card" style={{ padding: 12 }}>
        <CommandBar
          disabled={!initData || Boolean(authError)}
          placeholder={
            authError
              ? "Unauthorized (open from Telegram / configure initData verification)"
              : (initData ? "Ask ORION" : "Open via bot Web App button to enable commands")
          }
          onSubmit={async (text) => {
            setCommandError("");
            try {
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
      </footer>
    </div>
  );
}
