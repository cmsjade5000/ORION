import { useEffect, useMemo, useRef, useState } from "react";
import type { LiveState } from "../api/state";
import Node from "./Node";
import ConnectionLayer from "./ConnectionLayer";
import { useSmoothedActivities } from "../hooks/useSmoothedActivities";
import MiniNode from "./MiniNode";
import SideSilos from "./SideSilos";

export default function NetworkDashboard(props: {
  state: LiveState;
  token: string;
  telegramWebApp?: any;
  composerActive?: boolean;
  orionFlareAt?: number;
  onOpenFeed?: () => void;
  onOpenFiles?: () => void;
  unreadCount?: number;
  onOrionClick?: () => void;
  hiddenOrbitArtifactIds?: Set<string>;
  onHideOrbitArtifact?: (id: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 });
  const [now, setNow] = useState(() => Date.now());

  const agents = useMemo(() => props.state.agents, [props.state.agents]);
  const active = props.state.activeAgentId;
  const linkAgentId = props.state.link?.agentId ?? null;
  const linkDir = props.state.link?.dir ?? "out";
  const smoothed = useSmoothedActivities(agents);
  const orion = props.state.orion;
  const artifacts = props.state.artifacts || [];
  const feed = props.state.feed || [];
  const workflow = props.state.workflow || null;
  const composerActive = Boolean(props.composerActive);

  // Keep workflow around for connection visibility decisions, but we no longer show hop numbers on nodes.

  const wfStatusByAgent = useMemo(() => {
    const wf = workflow;
    return new Map((wf?.steps || []).map((s: any) => [String(s.agentId || ""), String(s.status || "")]));
  }, [workflow?.id, workflow?.steps]);

  const activeStepAgentId = useMemo(() => {
    const wf = workflow;
    const activeStep = (wf?.steps || []).find((s: any) => s && s.status === "active");
    return activeStep ? String((activeStep as any).agentId || "") : "";
  }, [workflow?.id, workflow?.steps]);

  // Detect "long-running" active workflow steps and render the agent as "busy" (yellow ring).
  // We can't trust `workflow.updatedAt` as a duration timer because it may update frequently.
  const activeStepStartRef = useRef<{ wfId: string | null; agentId: string | null; since: number }>({
    wfId: null,
    agentId: null,
    since: Date.now(),
  });

  useEffect(() => {
    if (!workflow || !activeStepAgentId) {
      activeStepStartRef.current = { wfId: null, agentId: null, since: Date.now() };
      return;
    }
    const cur = activeStepStartRef.current;
    if (cur.wfId !== workflow.id || cur.agentId !== activeStepAgentId) {
      activeStepStartRef.current = { wfId: workflow.id, agentId: activeStepAgentId, since: Date.now() };
    }
  }, [workflow?.id, activeStepAgentId]);

  useEffect(() => {
    if (!workflow || !activeStepAgentId) return;
    const t = window.setInterval(() => setNow(Date.now()), 600);
    return () => window.clearInterval(t);
  }, [workflow?.id, activeStepAgentId]);

  const isActiveStepDelayed = (() => {
    if (!workflow || !activeStepAgentId) return false;
    const since = activeStepStartRef.current.since;
    return now - since > 6500;
  })();

  const mini = useMemo(() => {
    const ids = ["PULSE", "NODE", "STRATUS"] as const;
    const out = new Map<
      (typeof ids)[number],
      { status: any; activity: any; wfStatus: string; engaged: boolean }
    >();

    for (const id of ids) {
      const a = agents.find((x) => x.id === id);
      const activity = (a ? (smoothed[a.id] ?? a.activity) : undefined) ?? "idle";
      const status = (a ? a.status : "idle") ?? "idle";
      const wfStatus = String(wfStatusByAgent.get(id) || "");
      const engaged =
        wfStatus === "active" ||
        status === "active" ||
        status === "busy" ||
        (activity && activity !== "idle");
      out.set(id, { status, activity, wfStatus, engaged });
    }
    return out;
  }, [agents, smoothed, wfStatusByAgent]);

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
    const cx = w / 2;

    // Hard layout inspired by Cory's mock.
    const D_MED = 78;
    const R_MED = D_MED / 2;
    const D_LG = 128;
    const R_LG = D_LG / 2;
    const D_SM = 44;
    const R_SM = D_SM / 2;
    const pad = 18;

    const yOrion = clamp(h * 0.44, R_LG + pad, h - (R_MED + R_SM + 120));
    // Top row: nudge a bit higher so it breathes.
    const yTop = clamp(yOrion - (R_LG + R_MED + 42), R_MED + pad, yOrion - 130);
    // Pull ATLAS and its child nodes closer to the bottom, while keeping a safe gap from ORION.
    const yAtlas = clamp(yOrion + (R_LG + R_MED + 54), yOrion + 130, h - (R_SM + pad + 48));
    const ySmall = clamp(yAtlas + (R_MED + R_SM + 24), yAtlas + 90, h - (R_SM + pad));

    const spreadTop = clamp(w * 0.26, 110, 190);
    const xPixel = clamp(cx - spreadTop, R_MED + pad, w - (R_MED + pad));
    const xEmber = clamp(cx, R_MED + pad, w - (R_MED + pad));
    const xLedger = clamp(cx + spreadTop, R_MED + pad, w - (R_MED + pad));

    const spreadSmall = clamp(w * 0.22, 86, 150);
    const xPulse = clamp(cx - spreadSmall, R_SM + pad, w - (R_SM + pad));
    const xNode = clamp(cx, R_SM + pad, w - (R_SM + pad));
    const xStratus = clamp(cx + spreadSmall, R_SM + pad, w - (R_SM + pad));

    // AEGIS indicator: pin to top-left (inset), not centered.
    const aegisX = pad;
    const aegisY = pad;

    const yPulse = ySmall;
    const yNode = clamp(ySmall + 14, ySmall, h - (R_SM + pad));
    const yStratus = ySmall;

    return {
      w,
      h,
      orion: { x: cx, y: yOrion },
      aegisIndicator: { x: aegisX, y: aegisY },
      top: {
        PIXEL: { x: xPixel, y: yTop },
        EMBER: { x: xEmber, y: yTop },
        LEDGER: { x: xLedger, y: yTop },
      },
      atlas: { x: cx, y: yAtlas },
      minis: {
        PULSE: { x: xPulse, y: yPulse },
        NODE: { x: xNode, y: yNode },
        STRATUS: { x: xStratus, y: yStratus },
      },
      extras: {
        cx,
        cy: yOrion,
        radius: clamp(Math.min(w, h) * 0.22, 86, 132),
        arc: { start: Math.PI * 0.15, end: Math.PI * 1.85 }, // avoid the top row
      },
    };
  }, [size.w, size.h]);

  return (
    <div className="orbit" ref={containerRef}>
      {(() => {
        const activeStepId = activeStepAgentId;
        const atlasActive = active === "ATLAS" || linkAgentId === "ATLAS" || activeStepId === "ATLAS";
        const linkTo =
          linkAgentId && (["PIXEL", "EMBER", "LEDGER", "ATLAS"] as const).includes(linkAgentId as any)
            ? linkAgentId
            : null;

        return (
          <>
            {/* Directional connectors should only represent actual "in-flight" communication. */}
            {linkTo ? (
              <ConnectionLayer
                key={`orion:link:${linkTo}:${linkDir}`}
                fromNodeId="ORION"
                toNodeId={linkTo}
                dir={linkDir}
                containerRef={containerRef}
              />
            ) : null}

            {/* ATLAS -> minis only when ATLAS is active in the current moment */}
            {atlasActive ? (
              <>
                {mini.get("PULSE")?.engaged ? <ConnectionLayer fromNodeId="ATLAS" toNodeId="PULSE" dir="out" containerRef={containerRef} /> : null}
                {mini.get("NODE")?.engaged ? <ConnectionLayer fromNodeId="ATLAS" toNodeId="NODE" dir="out" containerRef={containerRef} /> : null}
                {mini.get("STRATUS")?.engaged ? <ConnectionLayer fromNodeId="ATLAS" toNodeId="STRATUS" dir="out" containerRef={containerRef} /> : null}
              </>
            ) : null}
          </>
        );
      })()}

      {/* AEGIS: satellite + status dot (no node circle). */}
      {(() => {
        const a = agents.find((x) => x.id === "AEGIS");
        if (!a) return null;
        const badge = String((a as any).badge || "");
        const isAlarm = badge === "🚨" || a.status === "offline" || a.activity === "error";
        const isWarn = !isAlarm && badge === "⚠️";
        const isHighAlert = isAlarm && badge === "🚨";
        const isHealthy = !isAlarm && !isWarn;
        const dotCls = [
          "aegisDot",
          isAlarm ? "aegisDotAlarm" : isWarn ? "aegisDotWarn" : "aegisDotOk",
          isHighAlert ? "aegisDotHighAlert" : "",
        ].filter(Boolean).join(" ");
        const pinging = a.activity === "messaging";
        const title = isAlarm ? "AEGIS: alarm" : isWarn ? "AEGIS: warn" : pinging ? "AEGIS: heartbeat" : "AEGIS: ok";
        const pulseColor = isAlarm
          ? "rgba(255, 107, 107, 0.75)"
          : isWarn
            ? "rgba(255, 209, 102, 0.82)"
            : "rgba(124, 247, 193, 0.80)";
        return (
          <div
            className={[
              "aegisIndicator",
              pinging ? "aegisIndicatorPinging" : "",
              (pinging && isWarn) ? "aegisIndicatorNoAck" : "",
              isHighAlert ? "aegisIndicatorHighAlert" : "",
              isHealthy ? "aegisIndicatorAmbient" : "",
            ].filter(Boolean).join(" ")}
            title={title}
            aria-label={title}
            style={{
              left: `${layout.aegisIndicator.x}px`,
              top: `${layout.aegisIndicator.y}px`,
              ...(pinging ? ({ ["--aegis-pulse" as any]: pulseColor } as any) : {}),
            }}
          >
            <span className="aegisSatWrap" aria-hidden="true">
              {isHealthy ? <span className="aegisAmbient" aria-hidden="true" /> : null}
              {pinging ? <span className="aegisPulse" aria-hidden="true" /> : null}
              <span className="aegisSat" aria-hidden="true">🛰️</span>
            </span>
            <span className={dotCls} aria-hidden="true" />
          </div>
        );
      })()}

      {/* Central node */}
      {props.orionFlareAt ? (
        <div
          key={String(props.orionFlareAt)}
          className="orionRingFlare"
          aria-hidden="true"
          style={{
            position: "absolute",
            top: `${layout.orion.y}px`,
            left: `${layout.orion.x}px`,
            transform: "translate(-50%, -50%)",
          }}
        />
      ) : null}

      {(() => {
        const isDown = (orion?.status ?? "idle") === "offline" || orion?.badge === "❗";
        const isSuspect = orion?.badge === "⚠️";
        const isListening = composerActive && !isDown && !isSuspect && (orion?.status ?? "idle") === "idle";
        const processes = orion?.processes ?? [];
        const cls = [
          "nodeCentralNoLabel",
          "orionNode",
          isListening ? "orionListening" : "",
          isSuspect ? "orionSuspect" : "",
        ].filter(Boolean).join(" ");

        return (
          <Node
            id="ORION"
            label="ORION"
            hideLabel={true}
            status={orion?.status ?? (active ? "busy" : "idle")}
            processes={processes}
            badgeEmoji={orion?.badge ?? null}
            io={orion?.io ?? null}
            kind="central"
            active={Boolean(active || linkAgentId)}
            onClick={() => props.onOrionClick?.()}
            size="large"
            className={cls}
            style={{
              position: "absolute",
              top: `${layout.orion.y}px`,
              left: `${layout.orion.x}px`,
              transform: "translate(-50%, -50%)",
            }}
          />
        );
      })()}

      <div
        className="orionNameExternal"
        aria-hidden="true"
        style={{
          position: "absolute",
          left: `${layout.orion.x}px`,
          top: `${layout.orion.y + 74}px`,
          transform: "translate(-50%, 0)",
        }}
      >
        ORION
      </div>

      <SideSilos
        // Positions are offsets from ORION to look like Cory's sketch.
        cx={layout.orion.x}
        cy={layout.orion.y}
        artifacts={artifacts}
        feed={feed}
        token={props.token}
        telegramWebApp={props.telegramWebApp}
        onOpenFeed={props.onOpenFeed}
        onOpenFiles={props.onOpenFiles}
        unreadCount={props.unreadCount}
        hiddenOrbitArtifactIds={props.hiddenOrbitArtifactIds}
        onHideOrbitArtifact={props.onHideOrbitArtifact}
      />

      {(["PIXEL", "EMBER", "LEDGER", "ATLAS"] as const).map((id) => {
        const a = agents.find((x) => x.id === id);
        if (!a) return null;
        const pos =
          id === "ATLAS"
            ? layout.atlas
            : (layout.top as any)[id];

        const stepStatus = wfStatusByAgent.get(id);
        const derivedActivity =
          stepStatus === "failed"
            ? ("error" as const)
            : (smoothed[a.id] ?? a.activity);
        const derivedStatus =
          stepStatus === "active" && id === activeStepAgentId && isActiveStepDelayed && a.status !== "offline"
            ? ("busy" as const)
            : a.status;

        // If a workflow step failed, force the node to visually read as "error".
        const finalStatus =
          stepStatus === "failed" && a.status !== "offline"
            ? ("busy" as const) // status influences yellow; activity drives red ring
            : derivedStatus;

        return (
          <Node
            key={id}
            id={id}
            label={id}
            status={finalStatus}
            activity={derivedActivity}
            badgeEmoji={a.badge ?? null}
            kind="agent"
            size="medium"
            active={active === a.id}
            style={{
              left: `${pos.x}px`,
              top: `${pos.y}px`,
              transform: "translate(-50%, -50%)",
            }}
          />
        );
      })}

      <MiniNode
        id="PULSE"
        emoji="💓"
        status={mini.get("PULSE")?.status}
        activity={mini.get("PULSE")?.activity}
        active={Boolean(mini.get("PULSE")?.engaged)}
        style={{ left: `${layout.minis.PULSE.x}px`, top: `${layout.minis.PULSE.y}px`, transform: "translate(-50%, -50%)" }}
      />
      <MiniNode
        id="NODE"
        emoji="🧩"
        status={mini.get("NODE")?.status}
        activity={mini.get("NODE")?.activity}
        active={Boolean(mini.get("NODE")?.engaged)}
        style={{ left: `${layout.minis.NODE.x}px`, top: `${layout.minis.NODE.y}px`, transform: "translate(-50%, -50%)" }}
      />
      <MiniNode
        id="STRATUS"
        emoji="☁️"
        status={mini.get("STRATUS")?.status}
        activity={mini.get("STRATUS")?.activity}
        active={Boolean(mini.get("STRATUS")?.engaged)}
        style={{ left: `${layout.minis.STRATUS.x}px`, top: `${layout.minis.STRATUS.y}px`, transform: "translate(-50%, -50%)" }}
      />
    </div>
  );
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}
