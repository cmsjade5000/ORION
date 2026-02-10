import { useMemo, useRef, useState } from "react";
import type { Artifact, FeedItem } from "../api/state";
import { emojiForArtifact } from "../lib/artifact_icon";

type SiloItem = {
  key: string;
  emoji: string;
  title: string;
  onClick: () => void;
  // Only for artifacts: allow hold-to-hide.
  artifactId?: string;
};

function withToken(url: string, token: string) {
  if (!token) return url;
  if (!url.startsWith("/api/artifacts/")) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}token=${encodeURIComponent(token)}`;
}

export default function SideSilos(props: {
  cx: number;
  cy: number;
  artifacts: Artifact[];
  feed: FeedItem[];
  token: string;
  telegramWebApp?: any;
  onOpenFeed?: () => void;
  onOpenFiles?: () => void;
  unreadCount?: number;
  hiddenOrbitArtifactIds?: Set<string>;
  onHideOrbitArtifact?: (id: string) => void;
}) {
  const hidden = props.hiddenOrbitArtifactIds || new Set<string>();

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

  const files: SiloItem[] = useMemo(() => {
    const out: SiloItem[] = [];
    const arts = (props.artifacts || [])
      .filter((a) => a && typeof a.id === "string" && !hidden.has(a.id))
      .slice()
      .sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0));

    const top = arts.slice(0, 4);
    for (const a of top) {
      const url = withToken(String(a.url || ""), props.token);
      out.push({
        key: `art:${a.id}`,
        emoji: emojiForArtifact(a),
        title: a.name,
        artifactId: a.id,
        onClick: () => {
          if (!url) return;
          openLink(url);
        },
      });
    }

    const total = arts.length;
    if (total > top.length) {
      out.push({
        key: "files:more",
        emoji: "➕",
        title: "More files",
        onClick: () => props.onOpenFiles?.(),
      });
    }
    return out.slice(0, 5);
  }, [props.artifacts, props.token, hidden, props.onOpenFiles]);

  const chats: SiloItem[] = useMemo(() => {
    const out: SiloItem[] = [];
    const items = (props.feed || [])
      .filter((it) => it && it.kind === "response" && (it.agentId || "") === "ORION")
      .slice()
      .sort((a, b) => (b.ts || 0) - (a.ts || 0));
    const top = items.slice(0, 4);
    for (const it of top) {
      const text = String(it.text || "");
      const emoji = text.includes("?") ? "❓" : "💬";
      out.push({
        key: `chat:${it.id}`,
        emoji,
        title: text.slice(0, 120) || "Response",
        onClick: () => props.onOpenFeed?.(),
      });
    }
    if (items.length > top.length) {
      out.push({
        key: "chat:more",
        emoji: "➕",
        title: "More responses",
        onClick: () => props.onOpenFeed?.(),
      });
    }
    return out.slice(0, 5);
  }, [props.feed, props.onOpenFeed]);

  const HOLD_MS = 1400;
  const [holdingKey, setHoldingKey] = useState<string | null>(null);
  const holdTimerRef = useRef<number | null>(null);
  const suppressClickRef = useRef<Set<string>>(new Set());

  const startHold = (it: SiloItem) => {
    if (!it.artifactId || typeof props.onHideOrbitArtifact !== "function") return;
    if (holdTimerRef.current) window.clearTimeout(holdTimerRef.current);
    setHoldingKey(it.key);
    holdTimerRef.current = window.setTimeout(() => {
      suppressClickRef.current.add(it.key);
      setHoldingKey(null);
      try {
        props.telegramWebApp?.HapticFeedback?.impactOccurred?.("medium");
      } catch {
        // ignore
      }
      props.onHideOrbitArtifact?.(it.artifactId || "");
    }, HOLD_MS);
  };

  const cancelHold = (key: string) => {
    if (!holdTimerRef.current) return;
    window.clearTimeout(holdTimerRef.current);
    holdTimerRef.current = null;
    setHoldingKey((cur) => (cur === key ? null : cur));
  };

  const renderGrid = (items: SiloItem[], kind: "files" | "chat") => {
    const slots = items.slice(0, 4);
    const more = items.find((x) => x.key.endsWith(":more") || x.key.endsWith("more"));

    // Prefer using the 4th slot for ➕ when present.
    const final = slots.slice(0, 3);
    if (more) final.push(more);
    else if (slots[3]) final.push(slots[3]);

    while (final.length < 4) {
      final.push({
        key: `${kind}:empty:${final.length}`,
        emoji: "",
        title: "",
        onClick: () => {},
      });
    }

    return (
      <div className="siloGrid">
        {final.map((it) => {
          const isEmpty = !it.emoji;
          const isHolding = holdingKey === it.key;
          return (
            <button
              key={it.key}
              type="button"
              className={isEmpty ? "siloDot siloDotEmpty" : "siloDot"}
              title={it.title || undefined}
              onClick={(e) => {
                if (suppressClickRef.current.has(it.key)) {
                  suppressClickRef.current.delete(it.key);
                  e.preventDefault();
                  e.stopPropagation();
                  return;
                }
                if (isEmpty) return;
                it.onClick();
              }}
              onPointerDown={() => startHold(it)}
              onPointerUp={() => cancelHold(it.key)}
              onPointerCancel={() => cancelHold(it.key)}
              onPointerLeave={() => cancelHold(it.key)}
              onContextMenu={(e) => e.preventDefault()}
              aria-label={it.title || (kind === "files" ? "file" : "response")}
            >
              {isHolding ? (
                <svg
                  className="siloHold"
                  viewBox="0 0 48 48"
                  style={{ ["--hold-ms" as any]: `${HOLD_MS}ms` }}
                  aria-hidden="true"
                >
                  <circle className="siloHoldBg" cx="24" cy="24" r="20" />
                  <circle className="siloHoldRing" cx="24" cy="24" r="20" />
                </svg>
              ) : null}
              <span className="siloEmoji" aria-hidden="true">
                {it.emoji}
              </span>
            </button>
          );
        })}
      </div>
    );
  };

  const unread = Math.max(0, Number(props.unreadCount) || 0);

  return (
    <>
      <div className="sideSilo sideSiloLeft" style={{ left: `${props.cx}px`, top: `${props.cy}px` }}>
        {renderGrid(files, "files")}
        <button type="button" className="siloFooter" onClick={() => props.onOpenFiles?.()} aria-label="Open files">
          <span className="siloFooterIcon" aria-hidden="true">📁</span>
        </button>
      </div>

      <div className="sideSilo sideSiloRight" style={{ left: `${props.cx}px`, top: `${props.cy}px` }}>
        {renderGrid(chats, "chat")}
        <button type="button" className="siloFooter" onClick={() => props.onOpenFeed?.()} aria-label="Open responses">
          <span className="siloFooterIcon" aria-hidden="true">💬</span>
          {unread > 0 ? <span className="siloUnread" aria-label={`${unread} unread`} /> : null}
        </button>
      </div>
    </>
  );
}

