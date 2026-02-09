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

  const layout = useMemo(() => {
    const w = size.w || 520;
    const h = size.h || 520;

    // On iPhone portrait the orbit container can be tall and narrow. A circular orbit wastes
    // vertical space, so switch to an ellipse with independent X/Y radii.
    const portrait = h > w * 1.12;

    // Approximate padding needed to keep nodes + badge + shadow inside the stage.
    // (Orbit container already has its own inset via CSS.)
    const isNarrow = w < 400;
    const agentDiameter = isNarrow ? 68 : 74;
    const agentRadius = agentDiameter / 2;
    const badgeOverhang = 22; // badge + offset beyond the node circle
    const shadowOverhang = 14;
    const agentExtent = agentRadius + badgeOverhang + shadowOverhang;
    const safePadX = Math.max(72, agentExtent + 6);
    const safePadY = Math.max(72, agentExtent + 10);

    const cx = w / 2;
    const cy = h / 2;

    const rXMax = Math.max(96, w / 2 - safePadX);
    const rYMax = Math.max(96, h / 2 - safePadY);

    const rXMin = Math.min(portrait ? 118 : 140, rXMax);
    const rYMin = Math.min(portrait ? 146 : 140, rYMax);

    const rX = clamp(w * (portrait ? 0.34 : 0.36), rXMin, rXMax);
    const rY = clamp(h * (portrait ? 0.40 : 0.36), rYMin, rYMax);

    // Make the ring roughly follow the orbit while staying within the container.
    // Nodes should sit just inside the dashed ring, not on top of it.
    const ringPad = 18;
    const ringW = clamp(2 * (rX + agentRadius + ringPad), 220, w);
    const ringH = clamp(2 * (rY + agentRadius + ringPad), 220, h);

    return { w, h, cx, cy, rX, rY, ringW, ringH };
  }, [size.w, size.h]);

  return (
    <div className="orbit" ref={containerRef}>
      <div
        className="ring"
        style={{
          width: `${layout.ringW}px`,
          height: `${layout.ringH}px`,
        }}
      />

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
        const x = layout.cx + Math.cos(theta) * layout.rX;
        const y = layout.cy + Math.sin(theta) * layout.rY;

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
