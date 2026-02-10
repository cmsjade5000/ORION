import type { WorkflowState } from "../api/state";

function stepIcon(status: string) {
  switch (status) {
    case "active":
      return "⏳";
    case "done":
      return "✅";
    case "failed":
      return "⚠️";
    default:
      return "•";
  }
}

export default function WorkflowPanel(props: {
  workflow: WorkflowState | null | undefined;
  open: boolean;
  onToggle: () => void;
  variant?: "drawer" | "overlay";
}) {
  const wf = props.workflow || null;
  const steps = wf?.steps || [];
  const has = steps.length > 0;
  const variant = props.variant || "drawer";
  const isOpen = variant === "overlay" ? true : props.open;

  const summary = !has
    ? "Idle"
    : steps.map((s) => s.agentId).join(" → ");
  const running = Boolean(has && !props.open && (wf?.status === "running"));

  return (
    <div
      className={[
        "workflowPanel",
        isOpen ? "workflowPanelOpen" : "workflowPanelClosed",
        variant === "overlay" ? "workflowPanelOverlay" : "",
      ].filter(Boolean).join(" ")}
      aria-label="Workflow"
    >
      {variant === "drawer" ? (
        <button
          type="button"
          className="workflowHeader workflowHeaderButton"
          onClick={props.onToggle}
          aria-expanded={props.open}
        >
          <div className="workflowTitle">Workflow</div>
          <div className="workflowHint">
            {running ? <span className="workflowNotify" aria-label="workflow running" title="workflow running">⏳</span> : null}
            {summary} {props.open ? "\u25B4" : "\u25BE"}
          </div>
        </button>
      ) : (
        <div className="workflowOverlayHint" aria-hidden="true">{summary}</div>
      )}

      {isOpen && has ? (
        <div className="workflowList" role="list">
          {steps.map((s, idx) => (
            <div key={`${s.agentId}:${idx}`} className="workflowItem" role="listitem">
              <div className="workflowIcon" aria-hidden="true">{stepIcon(s.status)}</div>
              <div className="workflowStep">
                <span className="workflowAgent">{s.agentId}</span>
                <span className="workflowStatus">{s.status}</span>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
