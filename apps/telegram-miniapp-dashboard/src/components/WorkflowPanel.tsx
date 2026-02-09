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
}) {
  const wf = props.workflow || null;
  const steps = wf?.steps || [];
  const has = steps.length > 0;

  const summary = !has
    ? "Idle"
    : steps.map((s) => s.agentId).join(" → ");

  return (
    <div className={props.open ? "workflowPanel workflowPanelOpen" : "workflowPanel workflowPanelClosed"} aria-label="Workflow">
      <button
        type="button"
        className="workflowHeader workflowHeaderButton"
        onClick={props.onToggle}
        aria-expanded={props.open}
      >
        <div className="workflowTitle">Workflow</div>
        <div className="workflowHint">
          {summary} {props.open ? "\u25B4" : "\u25BE"}
        </div>
      </button>

      {props.open && has ? (
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

