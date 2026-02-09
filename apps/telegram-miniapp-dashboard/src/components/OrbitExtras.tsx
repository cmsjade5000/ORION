import { useMemo, useRef, useState } from "react";
import type { Artifact, FeedItem } from "../api/state";
import { emojiForArtifact } from "../lib/artifact_icon";

type ExtraItem = {
  key: string;
  emoji: string;
  title: string;
  onClick: () => void;
};

function withToken(url: string, token: string) {
  if (!token) return url;
  if (!url.startsWith("/api/artifacts/")) return url;
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}token=${encodeURIComponent(token)}`;
}

export default function OrbitExtras(props: {
  cx: number;
  cy: number;
  radius: number;
  artifacts: Artifact[];
  feed: FeedItem[];
  token: string;
  telegramWebApp?: any;
  onOpenFeed?: () => void;
  onOpenFiles?: () => void;
  hiddenOrbitArtifactIds?: Set<string>;
  onHideOrbitArtifact?: (id: string) => void;
}) {
  const HOLD_MS = 1400;
  const hiddenOrbit = props.hiddenOrbitArtifactIds || new Set<string>();
  const [dismissing, setDismissing] = useState<Set<string>>(() => new Set());
  const [holdingKey, setHoldingKey] = useState<string | null>(null);
  const holdTimerRef = useRef<number | null>(null);
  const suppressClickRef = useRef<Set<string>>(new Set());

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

  const items: ExtraItem[] = [];

  const arts = useMemo(() => {
    return (props.artifacts || [])
      .filter((a) => a && typeof a.id === "string" && !hiddenOrbit.has(a.id))
      .slice()
      .sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0))
      .slice(0, 7);
  }, [props.artifacts, hiddenOrbit]);

  for (const a of arts) {
    const url = withToken(String(a.url || ""), props.token);
    items.push({
      key: `art:${a.id}`,
      emoji: emojiForArtifact(a),
      title: a.name,
      onClick: () => {
        if (!url) return;
        openLink(url);
      },
    });
  }

  const totalVisibleArtifacts = (props.artifacts || []).filter((a) => a && typeof a.id === "string" && !hiddenOrbit.has(a.id)).length;
  if (totalVisibleArtifacts > arts.length && typeof props.onOpenFiles === "function") {
    items.push({
      key: "more",
      emoji: "➕",
      title: "More files",
      onClick: () => props.onOpenFiles?.(),
    });
  }

  // Follow-up indicator heuristic: if the newest response contains a question mark, show a "?" node.
  const maybeFollowup = (props.feed || []).find((it) => it && it.kind === "response" && typeof it.text === "string" && it.text.includes("?"));
  if (maybeFollowup) {
    items.push({
      key: `q:${maybeFollowup.id}`,
      emoji: "❓",
      title: "Follow-up question",
      onClick: () => props.onOpenFeed?.(),
    });
  }

  if (items.length === 0) return null;

  const r = Math.max(72, Math.min(132, props.radius));

  return (
    <div className="extrasLayer">
      {items.map((it, idx) => {
        const theta = (idx / Math.max(1, items.length)) * Math.PI * 2 - Math.PI / 2;
        const x = props.cx + Math.cos(theta) * r;
        const y = props.cy + Math.sin(theta) * r;
        const isArtifact = it.key.startsWith("art:");
        const artId = isArtifact ? it.key.slice("art:".length) : "";
        const isDismissing = dismissing.has(it.key);
        const isHolding = holdingKey === it.key;

        const startHold = () => {
          if (!isArtifact || !artId || typeof props.onHideOrbitArtifact !== "function") return;
          if (holdTimerRef.current) window.clearTimeout(holdTimerRef.current);
          setHoldingKey(it.key);
          holdTimerRef.current = window.setTimeout(() => {
            suppressClickRef.current.add(it.key);
            setHoldingKey(null);
            setDismissing((prev) => {
              const next = new Set(prev);
              next.add(it.key);
              return next;
            });
            try {
              props.telegramWebApp?.HapticFeedback?.impactOccurred?.("medium");
            } catch {
              // ignore
            }
            window.setTimeout(() => props.onHideOrbitArtifact?.(artId), 220);
          }, HOLD_MS);
        };

        const cancelHold = () => {
          if (!holdTimerRef.current) return;
          window.clearTimeout(holdTimerRef.current);
          holdTimerRef.current = null;
          setHoldingKey((cur) => (cur === it.key ? null : cur));
        };

        return (
          <button
            key={it.key}
            type="button"
            className={isDismissing ? "extraNode extraNodeDismissing" : "extraNode"}
            onClick={(e) => {
              if (suppressClickRef.current.has(it.key)) {
                suppressClickRef.current.delete(it.key);
                e.preventDefault();
                e.stopPropagation();
                return;
              }
              it.onClick();
            }}
            onPointerDown={() => startHold()}
            onPointerUp={() => cancelHold()}
            onPointerCancel={() => cancelHold()}
            onPointerLeave={() => cancelHold()}
            onContextMenu={(e) => e.preventDefault()}
            title={it.title}
            style={{
              left: `${x}px`,
              top: `${y}px`,
              transform: "translate(-50%, -50%)",
              animationDelay: `${idx * 180}ms`,
            }}
          >
            {isHolding ? (
              <svg
                className="extraHold"
                viewBox="0 0 48 48"
                style={{ ["--hold-ms" as any]: `${HOLD_MS}ms` }}
                aria-hidden="true"
              >
                <circle className="extraHoldBg" cx="24" cy="24" r="20" />
                <circle className="extraHoldRing" cx="24" cy="24" r="20" />
              </svg>
            ) : null}
            <span className="extraEmoji" aria-hidden="true">
              {it.emoji}
            </span>
          </button>
        );
      })}
    </div>
  );
}
