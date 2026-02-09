import { useEffect, useMemo, useRef, useState } from "react";
import type { LiveState } from "../api/state";
import Node from "./Node";
import ConnectionLayer from "./ConnectionLayer";
import { useSmoothedActivities } from "../hooks/useSmoothedActivities";

export default function NetworkDashboard(props: { state: LiveState }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 });

  const agents = useMemo(() => props.state.agents, [props.state.agents]);
  const active = props.state.activeAgentId;
  const smoothed = useSmoothedActivities(agents);
  const orion = props.state.orion;

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    let hasNonZero = false;
    const measure = () => {
      const r = el.getBoundingClientRect();
      // Guard against 0x0 during Telegram WebView initialization.
      if (r.width > 0 && r.height > 0) {
        hasNonZero = true;
        setSize({ w: r.width, h: r.height });
      }
    };

    measure();

    // ResizeObserver is ideal, but some embedded WebViews can be flaky/missing.
    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(() => measure());
      ro.observe(el);
    }

    const onResize = () => measure();
    window.addEventListener("resize", onResize);

    // Fallback: poll briefly until we have non-zero dimensions.
    let tries = 0;
    const t = window.setInterval(() => {
      tries += 1;
      measure();
      if (tries > 40 || hasNonZero) window.clearInterval(t);
    }, 100);

    return () => {
      if (ro) ro.disconnect();
      window.removeEventListener("resize", onResize);
      window.clearInterval(t);
    };
  }, []);

  return (
    <div className="orbit" ref={containerRef}>
      <div className="ring" />

      {/* Connections (ORION -> active agent) */}
      <ConnectionLayer activeAgentId={active} containerRef={containerRef} />

      {/* Central node */}
      <Node
        id="ORION"
        status={orion?.status ?? (active ? "busy" : "idle")}
        processes={orion?.processes}
        kind="central"
        active={!!active}
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
        }}
      />

      {/* Orbiting nodes
          Placeholder: node state animation.
          In v1 we only pulse the currently active agent.
      */}
      {agents.map((a, idx) => {
        // Fixed positions (readable + stable): evenly spaced around ORION.
        const theta = (idx / Math.max(1, agents.length)) * Math.PI * 2 - Math.PI / 2;
        const w = size.w || 520;
        const h = size.h || 520;
        const cx = w / 2;
        const cy = h / 2;

        // Keep nodes fully inside the canvas:
        // node radius ~37px + badge overflow + shadow -> budget ~80px.
        // iOS Telegram WebView is strict about clipping, so we pad more than we "need".
        const safePad = 104;
        const rMax = Math.max(110, Math.min(w, h) / 2 - safePad);
        const r = clamp(Math.min(w, h) * 0.36, 140, rMax);
        const x = cx + Math.cos(theta) * r;
        const y = cy + Math.sin(theta) * r;

        return (
          <Node
            key={a.id}
            id={a.id}
            status={a.status}
            activity={smoothed[a.id] ?? a.activity}
            kind="agent"
            active={active === a.id}
            style={{
              left: `${x}px`,
              top: `${y}px`,
              transform: "translate(-50%, -50%)",
            }}
          />
        );
      })}
    </div>
  );
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}
