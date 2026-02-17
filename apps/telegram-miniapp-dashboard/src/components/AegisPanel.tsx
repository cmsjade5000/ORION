import type { AgentState, FeedItem } from "../api/state";

function inferAegisStatus(aegis: AgentState | null | undefined): "ok" | "warn" | "alarm" {
  if (!aegis) return "warn";
  const badge = String((aegis as any).badge || "");
  const isAlarm = badge === "🚨" || aegis.status === "offline" || aegis.activity === "error";
  const isWarn = !isAlarm && badge === "⚠️";
  return isAlarm ? "alarm" : isWarn ? "warn" : "ok";
}

function statusLabel(st: "ok" | "warn" | "alarm") {
  if (st === "alarm") return "Alarm";
  if (st === "warn") return "Warn";
  return "OK";
}

export default function AegisPanel(props: {
  aegis: AgentState | null;
  items: FeedItem[];
}) {
  const st = inferAegisStatus(props.aegis);
  const badge = props.aegis ? String((props.aegis as any).badge || "") : "";
  const activity = props.aegis?.activity || "idle";
  const agentStatus = props.aegis?.status || "offline";

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "auto 1fr",
          gap: 12,
          alignItems: "center",
          padding: 12,
          borderRadius: 14,
          border: "1px solid rgba(255,255,255,0.10)",
          background: "rgba(0,0,0,0.18)",
        }}
      >
        <div style={{ fontSize: 26, lineHeight: 1 }} aria-hidden="true">🛰️</div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 900, letterSpacing: "0.04em" }}>
            AEGIS: {statusLabel(st)}
          </div>
          <div style={{ marginTop: 4, fontSize: 12, color: "rgba(255,255,255,0.72)" }}>
            status: {agentStatus} · activity: {activity}{badge ? ` · badge: ${badge}` : ""}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gap: 8 }}>
        <div style={{ fontSize: 12, color: "rgba(255,255,255,0.72)" }}>
          Recent health events
        </div>
        {props.items.length === 0 ? (
          <div className="pill">No AEGIS events yet</div>
        ) : (
          <div className="feedList" role="log" aria-live="polite">
            {props.items.slice(0, 30).map((it) => (
              <div key={it.id} className="feedItem">
                <div className="feedIcon" aria-hidden="true">
                  {it.icon || (it.kind === "artifact" ? "📎" : it.kind === "event" ? "•" : "💬")}
                </div>
                <div className="feedBody">
                  <div className="feedText">{it.text}</div>
                  <div className="feedMeta">
                    {it.agentId ? <span className="feedAgent">{it.agentId}</span> : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

