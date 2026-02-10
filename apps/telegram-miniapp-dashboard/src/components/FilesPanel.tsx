import type { Artifact } from "../api/state";
import { emojiForArtifact } from "../lib/artifact_icon";

function fmtBytes(n: number | null | undefined) {
  const v = typeof n === "number" && Number.isFinite(n) ? n : 0;
  if (v <= 0) return "";
  const kb = v / 1024;
  if (kb < 1024) return `${kb.toFixed(kb < 10 ? 1 : 0)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(mb < 10 ? 1 : 0)} MB`;
  const gb = mb / 1024;
  return `${gb.toFixed(gb < 10 ? 1 : 0)} GB`;
}

function withToken(url: string, token: string) {
  if (!token) return url;
  if (!url.startsWith("/api/artifacts/")) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}token=${encodeURIComponent(token)}`;
}

export default function FilesPanel(props: {
  artifacts: Artifact[];
  open: boolean;
  onToggle: () => void;
  token: string;
  telegramWebApp?: any;
  hiddenOrbitIds?: Set<string>;
  onUnhideOrbit?: (id: string) => void;
  onDeleteFromView?: (id: string) => void;
  variant?: "drawer" | "overlay";
}) {
  const variant = props.variant || "drawer";
  const isOpen = variant === "overlay" ? true : props.open;
  const items = (props.artifacts || [])
    .slice()
    .sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0));

  const hint = items.length === 0 ? "None" : `${items.length} ready`;

  const openLink = (url: string) => {
    const wa = props.telegramWebApp;
    if (typeof wa?.openLink === "function") {
      try {
        wa.openLink(url);
        return;
      } catch {
        // fall through
      }
    }
    window.open(url, "_blank", "noopener,noreferrer");
  };

  return (
    <div
      className={[
        "filesPanel",
        isOpen ? "filesPanelOpen" : "filesPanelClosed",
        variant === "overlay" ? "filesPanelOverlay" : "",
      ].filter(Boolean).join(" ")}
      aria-label="Files"
    >
      {variant === "drawer" ? (
        <button
          type="button"
          className="filesHeader filesHeaderButton"
          onClick={props.onToggle}
          aria-expanded={props.open}
        >
          <div className="filesTitle">Files</div>
          <div className="filesHint">
            {hint} {props.open ? "\u25B4" : "\u25BE"}
          </div>
        </button>
      ) : (
        <div className="filesOverlayHint" aria-hidden="true">{hint}</div>
      )}

      {isOpen ? (
        <div className="filesList" role="list">
          {items.map((a) => {
            const url = withToken(String(a.url || ""), props.token);
            const size = fmtBytes(a.sizeBytes);
            const hidden = props.hiddenOrbitIds?.has(a.id) ?? false;
            return (
              <div key={a.id} className="filesItem" role="listitem">
                <button
                  type="button"
                  className="filesOpen"
                  onClick={() => (url ? openLink(url) : null)}
                  title={a.name}
                >
                  <div className="filesIcon" aria-hidden="true">
                    {emojiForArtifact(a)}
                  </div>
                  <div className="filesBody">
                    <div className="filesName">{a.name}</div>
                    <div className="filesMeta">
                      <span>{a.mime}</span>
                      {size ? <span>{size}</span> : null}
                      {a.agentId ? <span>{a.agentId}</span> : null}
                    </div>
                  </div>
                </button>
                {hidden && typeof props.onUnhideOrbit === "function" ? (
                  <button
                    type="button"
                    className="filesDismiss"
                    onClick={() => props.onUnhideOrbit?.(a.id)}
                    title="Show bubble again"
                    aria-label="Show bubble again"
                  >
                    👁
                  </button>
                ) : null}
                {typeof props.onDeleteFromView === "function" ? (
                  <button
                    type="button"
                    className="filesDismiss"
                    onClick={() => props.onDeleteFromView?.(a.id)}
                    title="Delete from view"
                    aria-label="Delete from view"
                  >
                    🗑
                  </button>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
