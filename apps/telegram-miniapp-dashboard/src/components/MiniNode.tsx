import type { AgentActivity, AgentStatus } from "../api/state";
import type { CSSProperties } from "react";

export default function MiniNode(props: {
  id: string;
  emoji: string;
  status?: AgentStatus;
  activity?: AgentActivity;
  active?: boolean;
  title?: string;
  style?: CSSProperties;
}) {
  return (
    <div
      className={["miniNode", props.active ? "miniNodeActive" : ""].filter(Boolean).join(" ")}
      data-node-id={props.id}
      data-status={props.status}
      data-activity={props.activity}
      title={props.title || props.id}
      style={props.style}
      aria-label={props.title || props.id}
    >
      {props.active ? <div className="miniNodePulse" aria-hidden="true" /> : null}
      <span className="miniNodeEmoji" aria-hidden="true">{props.emoji}</span>
    </div>
  );
}
