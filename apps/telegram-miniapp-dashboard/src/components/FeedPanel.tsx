import type { FeedItem } from "../api/state";

function relTime(ts: number, now: number) {
  const d = Math.max(0, now - ts);
  if (d < 10_000) return "now";
  const s = Math.floor(d / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h`;
}

export default function FeedPanel(props: {
  items: FeedItem[];
  open: boolean;
  onToggle: () => void;
  unreadCount?: number;
  variant?: "drawer" | "overlay";
  maxItems?: number;
  onRerun?: (text: string) => void;
  onShare?: (text: string) => void;
}) {
  const variant = props.variant || "drawer";
  const isOpen = variant === "overlay" ? true : props.open;
  const limit = Math.max(1, Math.min(60, Number(props.maxItems || (variant === "overlay" ? 30 : 10))));
  const items = (props.items || []).slice(0, limit);
  const now = Date.now();

  const hint = items.length === 0 ? "Waiting" : `${items.length} recent`;
  const unread = Math.max(0, Number(props.unreadCount || 0));

  return (
    <div
      className={[
        "feedPanel",
        isOpen ? "feedPanelOpen" : "feedPanelClosed",
        variant === "overlay" ? "feedPanelOverlay" : "",
      ].filter(Boolean).join(" ")}
      aria-label="Responses"
    >
      {variant === "drawer" ? (
        <button
          type="button"
          className="feedHeader feedHeaderButton"
          onClick={props.onToggle}
          aria-expanded={props.open}
        >
          <div className="feedTitle">Responses</div>
          <div className="feedHint">
            {!props.open && unread > 0 ? (
              <span className="feedNotify feedNotifyPulse" aria-label={`${unread} new`}>
                <span className="feedNotifyIcon" aria-hidden="true">🔔</span>
                <span className="feedNotifyCount" aria-hidden="true">{unread > 9 ? "9+" : String(unread)}</span>
              </span>
            ) : null}
            {hint} {props.open ? "\u25B4" : "\u25BE"}
          </div>
        </button>
      ) : (
        <div className="feedOverlayHint" aria-hidden="true">{hint}</div>
      )}

      {isOpen ? (
        <div className="feedList" role="log" aria-live="polite">
          {items.map((it) => (
            <div key={it.id} className="feedItem">
              <div className="feedIcon" aria-hidden="true">
                {it.icon || (it.kind === "artifact" ? "📎" : it.kind === "event" ? "•" : "💬")}
              </div>
              <div className="feedBody">
                <div className="feedText">{it.text}</div>
                {(it.kind === "response" && (it.agentId || "") === "ORION" && (props.onRerun || props.onShare)) ? (
                  <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                    {props.onRerun ? (
                      <button
                        type="button"
                        className="button buttonGhost"
                        onClick={() => props.onRerun?.(it.text)}
                        aria-label="Re-run"
                        title="Re-run / tweak"
                      >
                        ↩︎ Re-run
                      </button>
                    ) : null}
                    <button
                      type="button"
                      className="button buttonGhost"
                      onClick={async () => {
                        try {
                          await navigator.clipboard?.writeText?.(it.text);
                        } catch {
                          // ignore (clipboard can be blocked in some webviews)
                        }
                      }}
                      aria-label="Copy"
                      title="Copy"
                    >
                      ⧉ Copy
                    </button>
                    {props.onShare ? (
                      <button
                        type="button"
                        className="button buttonGhost"
                        onClick={() => props.onShare?.(it.text)}
                        aria-label="Share"
                        title="Share to Telegram chat"
                      >
                        ⤴︎ Share
                      </button>
                    ) : null}
                  </div>
                ) : null}
                <div className="feedMeta">
                  <span className="feedTime">{relTime(it.ts, now)}</span>
                  {it.agentId ? <span className="feedAgent">{it.agentId}</span> : null}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
