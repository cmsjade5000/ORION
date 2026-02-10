import { useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import type { ActiveLink, LinkDir } from "../api/state";

type Point = { x: number; y: number };
type NodeGeom = { c: Point; r: number };

function geomOf(el: HTMLElement, relativeTo: DOMRect): NodeGeom {
  const r = el.getBoundingClientRect();
  return {
    c: {
      x: r.left - relativeTo.left + r.width / 2,
      y: r.top - relativeTo.top + r.height / 2,
    },
    r: Math.max(8, Math.min(r.width, r.height) / 2),
  };
}

/**
 * Connection animation (WebView-safe).
 *
 * SVG markers + clipPaths are flaky in Telegram iOS WebViews, so we render a rotated div "track"
 * and animate small chevrons along it to indicate direction.
 */
export default function ConnectionLayer(props: {
  // Back-compat: if `toNodeId` not provided, this uses `link?.agentId ?? activeAgentId`.
  activeAgentId?: string | null;
  link?: ActiveLink | null;
  containerRef: RefObject<HTMLDivElement>;
  fromNodeId?: string;
  toNodeId?: string | null;
  dir?: LinkDir;
  suppressToNodeIds?: Set<string>;
}) {
  const fromNodeId = props.fromNodeId || "ORION";
  const toNodeId = props.toNodeId ?? (props.link?.agentId ?? props.activeAgentId ?? null);
  const dir = props.dir ?? (props.link?.dir ?? "out");
  const suppressed = props.suppressToNodeIds?.has(String(toNodeId || "")) ?? false;

  const key = useMemo(() => {
    return toNodeId ? `${fromNodeId}:${dir}:${toNodeId}` : "none";
  }, [fromNodeId, dir, toNodeId]);

  const [from, setFrom] = useState<Point | null>(null);
  const [to, setTo] = useState<Point | null>(null);
  const [visible, setVisible] = useState(false);
  const unmountTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const container = props.containerRef.current;
    if (!container) return;

    const update = () => {
      const stageRect = container.getBoundingClientRect();
      const fromEl = container.querySelector<HTMLElement>(`[data-node-id='${fromNodeId}']`);
      const target = toNodeId
        ? container.querySelector<HTMLElement>(`[data-node-id='${toNodeId}']`)
        : null;

      if (!fromEl || !target || suppressed) {
        setVisible(false);
        return;
      }

      const a = geomOf(fromEl, stageRect);
      const b = geomOf(target, stageRect);
      // Directionality: out means from -> to, in means to -> from.
      const start = dir === "in" ? b : a;
      const end = dir === "in" ? a : b;
      const dx = end.c.x - start.c.x;
      const dy = end.c.y - start.c.y;
      const len = Math.hypot(dx, dy);
      if (!len) {
        setFrom(start.c);
        setTo(end.c);
        return;
      }

      const ux = dx / len;
      const uy = dy / len;
      // Keep the line very close to node edges (Cory prefers longer connectors).
      // Use small, radius-scaled padding so it doesn't visually cut into the node fill.
      const padFrom = Math.max(10, Math.min(18, start.r * 0.18));
      const padTo = Math.max(12, Math.min(20, end.r * 0.20));

      setFrom({ x: start.c.x + ux * (start.r + padFrom), y: start.c.y + uy * (start.r + padFrom) });
      setTo({ x: end.c.x - ux * (end.r + padTo), y: end.c.y - uy * (end.r + padTo) });
      setVisible(true);
    };

    update();
    const t = toNodeId ? window.setInterval(update, 250) : null;
    const onResize = () => update();
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      if (t) window.clearInterval(t);
    };
  }, [props.containerRef, fromNodeId, toNodeId, dir, suppressed, key]);

  // When the link is removed, fade out first, then unmount.
  useEffect(() => {
    if (unmountTimerRef.current) {
      window.clearTimeout(unmountTimerRef.current);
      unmountTimerRef.current = null;
    }
    if (visible) return;
    // If we don't have geometry yet, just stay unmounted.
    if (!from || !to) return;
    unmountTimerRef.current = window.setTimeout(() => {
      setFrom(null);
      setTo(null);
    }, 240);
    return () => {
      if (unmountTimerRef.current) window.clearTimeout(unmountTimerRef.current);
      unmountTimerRef.current = null;
    };
  }, [visible, from, to]);

  if (!from || !to) return null;

  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const len = Math.max(1, Math.hypot(dx, dy));
  const deg = (Math.atan2(dy, dx) * 180) / Math.PI;
  const chevrons = Math.max(3, Math.min(7, Math.floor(len / 58)));

  return (
    <div className="connLayer" aria-hidden="true">
      <div
        className={visible ? "connTrack" : "connTrack connTrackHidden"}
        style={{
          left: `${from.x}px`,
          top: `${from.y}px`,
          width: `${len}px`,
          transform: `rotate(${deg}deg)`,
          ["--conn-len" as any]: `${len}px`,
        }}
        data-conn={key}
      >
        <div className="connStroke" />
        {visible ? (
          Array.from({ length: chevrons }).map((_, i) => (
            <span
              key={i}
              className="connChevron"
              style={{
                ["--conn-delay" as any]: `${-i * 180}ms`,
              }}
            />
          ))
        ) : null}
      </div>
    </div>
  );
}
