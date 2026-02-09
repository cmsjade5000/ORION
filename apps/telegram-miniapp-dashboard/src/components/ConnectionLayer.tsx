import { useEffect, useId, useMemo, useState } from "react";
import type { RefObject } from "react";
import type { ActiveLink } from "../api/state";

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
 * Placeholder: connection animation.
 *
 * Draws a dashed animated line from ORION to the active agent.
 * Later you can extend this to show event bursts, message labels, and per-agent streams.
 */
export default function ConnectionLayer(props: {
  activeAgentId: string | null;
  link?: ActiveLink | null;
  containerRef: RefObject<HTMLDivElement>;
}) {
  const rid = useId();
  const [from, setFrom] = useState<Point | null>(null);
  const [to, setTo] = useState<Point | null>(null);
  const [holeA, setHoleA] = useState<NodeGeom | null>(null);
  const [holeB, setHoleB] = useState<NodeGeom | null>(null);
  const [vb, setVb] = useState<{ w: number; h: number } | null>(null);

  const agentId = props.link?.agentId ?? props.activeAgentId;
  const dir = props.link?.dir ?? "out";

  const key = useMemo(() => {
    return agentId ? `${dir}:${agentId}` : "none";
  }, [agentId, dir]);

  const maskId = useMemo(() => {
    // Stable-ish per-connection id so Safari doesn't reuse masks incorrectly.
    // include useId() so multiple ConnectionLayer instances never collide.
    const safeRid = rid.replace(/[^a-zA-Z0-9_\\-]/g, "_");
    return `clip_${safeRid}_${key.replace(/[^a-zA-Z0-9_\\-]/g, "_")}`;
  }, [key, rid]);

  const markerId = useMemo(() => {
    const safeRid = rid.replace(/[^a-zA-Z0-9_\\-]/g, "_");
    return `arrow_${safeRid}_${key.replace(/[^a-zA-Z0-9_\\-]/g, "_")}`;
  }, [key, rid]);

  useEffect(() => {
    const container = props.containerRef.current;
    if (!container) return;

    const update = () => {
      const stageRect = container.getBoundingClientRect();
      const orion = container.querySelector<HTMLElement>("[data-node-id='ORION']");
      const target = agentId
        ? container.querySelector<HTMLElement>(`[data-node-id='${agentId}']`)
        : null;

      if (!orion || !target) {
        setFrom(null);
        setTo(null);
        setHoleA(null);
        setHoleB(null);
        setVb(null);
        return;
      }

      const a = geomOf(orion, stageRect);
      const b = geomOf(target, stageRect);
      // Directionality: out means ORION -> agent, in means agent -> ORION.
      const start = dir === "in" ? b : a;
      const end = dir === "in" ? a : b;
      const dx = end.c.x - start.c.x;
      const dy = end.c.y - start.c.y;
      const len = Math.hypot(dx, dy);
      if (!len) {
        setFrom(start.c);
        setTo(end.c);
        setHoleA(a);
        setHoleB(b);
        setVb({ w: stageRect.width, h: stageRect.height });
        return;
      }

      // Shorten the line so it ends at each node edge. This prevents the dashed
      // line from showing through semi-transparent node fills in iOS WebViews.
      const ux = dx / len;
      const uy = dy / len;

      // Extra padding keeps the line outside outlines/pulse/glow.
      // (Bounding rect does not include the pulse child, so we budget for it.)
      const padFrom = 28;
      const padTo = 32;

      setFrom({ x: start.c.x + ux * (start.r + padFrom), y: start.c.y + uy * (start.r + padFrom) });
      setTo({ x: end.c.x - ux * (end.r + padTo), y: end.c.y - uy * (end.r + padTo) });
      setHoleA(a);
      setHoleB(b);
      setVb({ w: stageRect.width, h: stageRect.height });
    };

    // Nodes are fixed-position now; update on resize + a light interval while active
    // to handle Telegram WebView layout shifts.
    update();
    const t = agentId ? window.setInterval(update, 250) : null;

    const onResize = () => update();
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      if (t) window.clearInterval(t);
    };
  }, [agentId, dir, props.containerRef, key]);

  if (!from || !to || !holeA || !holeB || !vb) return null;

  // iOS Telegram WebViews have flaky SVG masking; use a clipPath with even-odd fill
  // to "punch holes" where nodes are, so the line cannot appear *inside* nodes.
  const w = Math.max(1, vb.w);
  const h = Math.max(1, vb.h);

  const circlePath = (cx: number, cy: number, r: number) => {
    const rr = Math.max(0, r);
    // Two arcs make a circle; works well across browsers.
    return `M ${cx - rr} ${cy} a ${rr} ${rr} 0 1 0 ${rr * 2} 0 a ${rr} ${rr} 0 1 0 ${-rr * 2} 0`;
  };

  const punch = [
    `M 0 0 H ${w} V ${h} H 0 Z`,
    circlePath(holeA.c.x, holeA.c.y, holeA.r + 22),
    circlePath(holeB.c.x, holeB.c.y, holeB.r + 24),
  ].join(" ");

  return (
    <svg
      className="connectionSvg"
      aria-hidden="true"
      width="100%"
      height="100%"
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
    >
      <defs>
        <clipPath id={maskId} clipPathUnits="userSpaceOnUse">
          {/* evenodd: rect visible, circles removed */}
          <path d={punch} fillRule="evenodd" clipRule="evenodd" />
        </clipPath>
        {/* Subtle arrow head. Direction is controlled by swapping endpoints based on `dir`. */}
        <marker
          id={markerId}
          viewBox="0 0 10 10"
          refX="8.5"
          refY="5"
          markerWidth="5"
          markerHeight="5"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(124, 247, 193, 0.95)" />
        </marker>
      </defs>

      <line
        className="connectionLine"
        x1={from.x}
        y1={from.y}
        x2={to.x}
        y2={to.y}
        clipPath={`url(#${maskId})`}
      />

      {/* "Packet" that travels along the link to make direction obvious. */}
      <line
        className="connectionPacket"
        x1={from.x}
        y1={from.y}
        x2={to.x}
        y2={to.y}
        clipPath={`url(#${maskId})`}
        markerEnd={`url(#${markerId})`}
      />
    </svg>
  );
}
