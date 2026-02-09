import { useEffect, useMemo, useState } from "react";
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
  const [commandError, setCommandError] = useState<string>("");
  const [state, setState] = useState<LiveState>({
    ts: Date.now(),
    activeAgentId: null,
    agents: DEFAULT_AGENTS.map((id) => ({ id, status: "idle" as const })),
  });

  // Telegram init: safe to run even when not inside Telegram.
  useEffect(() => {
    const tg = initTelegram();
    if (tg) {
      setInitData(tg.initData);
      setPlatform(`${tg.platform} (tg v${tg.version})`);
    }
  }, []);

  // Prefer push updates via SSE. Fall back to polling if SSE is unavailable or fails.
  useEffect(() => {
    let cancelled = false;
    let conn: { close: () => void } | null = null;

    const start = async () => {
      if (typeof EventSource === "undefined") {
        setPolling(true);
        return;
      }

      setPolling(false);
      setStreamStatus("connecting");

      try {
        const auth = await getStreamToken(initData);
        if (cancelled) return;

        conn = connectStateStream({
          token: auth.token,
          onState: (s) => setState(s),
          onStatus: (st) => {
            setStreamStatus(st);
            if (st === "error") {
              // Degrade to polling if the stream drops (tunnels/proxies can do this).
              setPolling(true);
              if (conn) conn.close();
            }
          },
        });
      } catch {
        // Any failure should degrade to polling.
        setPolling(true);
        setStreamStatus("error");
      }
    };

    start();
    return () => {
      cancelled = true;
      if (conn) conn.close();
    };
  }, [initData]);

  useEffect(() => {
    if (!polling) return;
    let cancelled = false;

    const tick = async () => {
      try {
        const next = await fetchLiveState({ initData });
        if (!cancelled) setState(next);
      } catch {
        // Keep UI up even if API is offline.
      }
    };

    tick();
    const t = window.setInterval(tick, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, [polling, initData]);

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
          disabled={!initData}
          placeholder={initData ? "Ask ORION (placeholder)" : "Open via bot Web App button to enable commands"}
          onSubmit={async (text) => {
            setCommandError("");
            try {
              // Send to backend so ORION can later route this into task packets/sessions.
              const res = await submitCommand({ initData, text });
              // eslint-disable-next-line no-console
              console.log("command.accepted", res);
            } catch (e) {
              const msg = e instanceof Error ? e.message : String(e);
              setCommandError(msg);
            }
          }}
        />
        {commandError ? (
          <div style={{ marginTop: 8, fontSize: 12, color: "#ffb4a2" }}>
            {commandError}
          </div>
        ) : null}
      </footer>
    </div>
  );
}
