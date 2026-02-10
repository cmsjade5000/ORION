import type { AgentStatus } from "../api/state";
import type { AgentActivity } from "../api/state";
import type { CSSProperties } from "react";
import { useEffect, useRef, useState } from "react";

function activityEmoji(a: AgentActivity | undefined): string | null {
  if (!a || a === "idle") return null;
  switch (a) {
    case "thinking":
      return "🧠";
    case "search":
      return "🔎";
    case "files":
      return "📁";
    case "tooling":
      return "🛠️";
    case "messaging":
      return "✉️";
    case "error":
      return "⚠️";
    default:
      return "•";
  }
}

export default function Node(props: {
  id: string;
  label?: string;
  status: AgentStatus;
  activity?: AgentActivity;
  onClick?: () => void;
  size?: "large" | "medium";
  // Central node only: orchestration indicators (emojis) shown instead of status words.
  processes?: string[];
  // Central node only: IO phase (controls the status subline).
  io?: "receiving" | "dispatching" | null;
  // Floating badge emoji. For agents this can override activity. For ORION this is used for process clarity.
  badgeEmoji?: string | null;
  kind: "central" | "agent";
  active?: boolean;
  className?: string;
  style?: CSSProperties;
}) {
  const lit =
    props.kind === "agent" &&
    (props.status === "active" ||
      props.status === "busy" ||
      (props.activity && props.activity !== "idle"));

  const sizeCls = props.size === "large" ? "nodeSizeLarge" : "nodeSizeMedium";
  const cls = ["node", sizeCls, props.kind === "central" ? "nodeCentral" : "", props.active ? "nodeActive" : "", props.className || ""]
    .concat(lit ? ["nodeLit"] : [])
    .filter(Boolean)
    .join(" ");

  const emoji =
    props.kind === "agent"
      ? (props.badgeEmoji ?? activityEmoji(props.activity))
      : (props.badgeEmoji ?? null);
  const [curEmoji, setCurEmoji] = useState<string | null>(emoji);
  const [prevEmoji, setPrevEmoji] = useState<string | null>(null);
  const curRef = useRef<string | null>(emoji);

  useEffect(() => {
    if (emoji === curRef.current) return;
    setPrevEmoji(curRef.current);
    setCurEmoji(emoji);
    curRef.current = emoji;
    const t = window.setTimeout(() => setPrevEmoji(null), 260);
    return () => window.clearTimeout(t);
  }, [emoji]);

  // ORION central process emoji rotation (smooth, not flickery).
  const processes = props.kind === "central" ? (props.processes ?? []) : [];
  const [procIdx, setProcIdx] = useState(0);
  const curProc = processes.length ? processes[procIdx % processes.length] : null;
  const [curProcEmoji, setCurProcEmoji] = useState<string | null>(curProc);
  const [prevProcEmoji, setPrevProcEmoji] = useState<string | null>(null);
  const procRef = useRef<string | null>(curProc);

  useEffect(() => {
    if (props.kind !== "central") return;
    // Reset to first when process list changes.
    setProcIdx(0);
  }, [props.kind, processes.join("|")]);

  useEffect(() => {
    if (props.kind !== "central") return;
    if (!processes.length) return;
    if (typeof window === "undefined") return;
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    // Rotate at a human-readable cadence.
    const t = window.setInterval(() => setProcIdx((n) => n + 1), 1500);
    return () => window.clearInterval(t);
  }, [props.kind, processes.length]);

  useEffect(() => {
    if (props.kind !== "central") return;
    if (curProc === procRef.current) return;
    setPrevProcEmoji(procRef.current);
    setCurProcEmoji(curProc);
    procRef.current = curProc;
    const t = window.setTimeout(() => setPrevProcEmoji(null), 260);
    return () => window.clearTimeout(t);
  }, [props.kind, curProc]);

  return (
    <div
      className={cls}
      style={props.style}
      data-node-id={props.id}
      data-status={props.status}
      data-activity={props.kind === "agent" ? (props.activity ?? "idle") : undefined}
      onClick={() => props.onClick?.()}
      role={props.onClick ? "button" : undefined}
      tabIndex={props.onClick ? 0 : undefined}
      onKeyDown={(e) => {
        if (!props.onClick) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          props.onClick();
        }
      }}
    >
      {props.active ? <div className="nodePulse" aria-hidden="true" /> : null}
      {(curEmoji || prevEmoji) ? (
        <div
          className={["nodeBadge", curEmoji ? "nodeBadgeOn" : "nodeBadgeOff"].join(" ")}
          aria-label={
            props.kind === "agent"
              ? (props.activity ? `activity: ${props.activity}` : "activity: idle")
              : (props.badgeEmoji ? `orion: ${props.badgeEmoji}` : "orion: idle")
          }
        >
          {prevEmoji ? (
            <span key={`${prevEmoji}-out`} className="nodeBadgeEmoji nodeBadgeEmojiOut" aria-hidden="true">
              {prevEmoji}
            </span>
          ) : null}
          {curEmoji ? (
            <span key={`${curEmoji}-in`} className="nodeBadgeEmoji nodeBadgeEmojiIn" aria-hidden="true">
              {curEmoji}
            </span>
          ) : null}
        </div>
      ) : null}
      <div>
        <div className="nodeLabel">{props.label || props.id}</div>
        {props.kind === "central" ? (
          <>
            <div className="nodeSub nodeSubCentral" aria-hidden="true">
            {prevProcEmoji ? (
              <span key={`${prevProcEmoji}-out`} className="nodeProcEmoji nodeProcEmojiOut">
                {prevProcEmoji}
              </span>
            ) : null}
            {curProcEmoji ? (
              <span key={`${curProcEmoji}-in`} className="nodeProcEmoji nodeProcEmojiIn">
                {curProcEmoji}
              </span>
            ) : (
              <span className="nodeProcEmoji nodeProcEmojiIdle"> </span>
            )}
            </div>
          </>
        ) : (
          <div className="nodeSub">{props.status}</div>
        )}
      </div>
    </div>
  );
}
