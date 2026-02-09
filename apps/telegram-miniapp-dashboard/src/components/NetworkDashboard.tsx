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
  const linkAgentId = props.state.link?.agentId ?? null;
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

    // Special portrait layout: AEGIS is "remote" (top centered + slightly clipped),
    // other agents sit in the corners around ORION.
    const hasAegis = agents.some((a) => a.id === "AEGIS");
    const frameMode = portrait && agents.length === 5 && hasAegis;

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

    // Frame positions
    // Corner padding: keep nodes mostly inside the stage, but intentionally tighter in portrait
    // so the layout uses more of the screen.
    const cornerPadX = clamp(agentExtent * 0.90, 58, Math.max(58, w / 2 - agentRadius - 14));
    const cornerPadY = clamp(agentExtent * 0.98, 68, Math.max(68, h / 2 - agentRadius - 18));

    const positions: Record<string, { x: number; y: number; variant?: "remote" }> = {};
    if (frameMode) {
      // Put AEGIS a bit above the top edge so it feels "remote" / partially off-canvas.
      positions.AEGIS = { x: cx, y: -agentRadius * 0.18, variant: "remote" };
      positions.ATLAS = { x: cornerPadX, y: cornerPadY };
      positions.EMBER = { x: w - cornerPadX, y: cornerPadY };
      positions.PIXEL = { x: cornerPadX, y: h - cornerPadY };
      positions.LEDGER = { x: w - cornerPadX, y: h - cornerPadY };
    }

    return { w, h, cx, cy, rX, rY, ringW, ringH, portrait, frameMode, positions };
  }, [size.w, size.h, agents]);

  return (
    <div className="orbit" ref={containerRef}>
      {layout.frameMode ? null : (
        <div
          className="ring"
          style={{
            width: `${layout.ringW}px`,
            height: `${layout.ringH}px`,
          }}
        />
      )}

      {/* Connections (ORION -> active agent) */}
      <ConnectionLayer activeAgentId={active} link={props.state.link ?? null} containerRef={containerRef} />

      {/* Central node */}
      <Node
        id="ORION"
        status={orion?.status ?? (active ? "busy" : "idle")}
        processes={orion?.processes}
        badgeEmoji={orion?.badge ?? null}
        io={orion?.io ?? null}
        kind="central"
        active={Boolean(active || linkAgentId)}
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
        const framePos = layout.frameMode ? layout.positions[a.id] : null;
        // Default: evenly spaced around ORION.
        const theta = (idx / Math.max(1, agents.length)) * Math.PI * 2 - Math.PI / 2;
        const x = framePos ? framePos.x : layout.cx + Math.cos(theta) * layout.rX;
        const y = framePos ? framePos.y : layout.cy + Math.sin(theta) * layout.rY;
        const remote = framePos?.variant === "remote";

        return (
          <Node
            key={a.id}
            id={a.id}
            status={a.status}
            activity={smoothed[a.id] ?? a.activity}
            badgeEmoji={a.badge ?? null}
            kind="agent"
            active={active === a.id}
            className={remote ? "nodeRemote" : undefined}
            style={{
              left: `${x}px`,
              top: `${y}px`,
              transform: remote ? "translate(-50%, -50%) scale(0.86)" : "translate(-50%, -50%)",
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
