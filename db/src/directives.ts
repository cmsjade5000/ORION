import type {
  DirectiveBinding,
  DirectiveEventType,
  EventLogEntry,
  OrionEventPayloadMap,
  TaskPacketType
} from "./types";

const BINDINGS: DirectiveBinding[] = [
  {
    directive: "DAILY_SYNC",
    label: "Daily Sync",
    objectiveHint: "Example: Keep all agents aligned on this week's priorities.",
    actionSummary: "Runs an ORION-led cohesion sync across core specialists and reports drift."
  },
  {
    directive: "RUN_DIAGNOSTICS",
    label: "Run Diagnostics",
    objectiveHint: "Example: Find blockers before I start focused work.",
    actionSummary: "Runs a deterministic Gateway diagnostic sweep and returns actionable issues."
  },
  {
    directive: "FLUSH_CACHE",
    label: "Flush Cache",
    objectiveHint: "Example: Reduce stale context and restore signal quality.",
    actionSummary: "Runs a safe context-hygiene pass to clean stale queues and summarize reset actions."
  },
  {
    directive: "INJECT_TASK_PACKET",
    label: "Inject Task Packet",
    objectiveHint: "Example: Push a refactor packet for this workspace.",
    actionSummary: "Creates and executes a specialist task packet aligned to your objective."
  }
];

function asObjective(payload: unknown): string {
  if (!payload || typeof payload !== "object") {
    return "";
  }
  const value = (payload as { objective?: unknown }).objective;
  return typeof value === "string" ? value.trim() : "";
}

function asTaskType(payload: unknown): TaskPacketType | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const value = (payload as { type?: unknown }).type;
  if (
    value === "research" ||
    value === "refactor" ||
    value === "report" ||
    value === "triage" ||
    value === "automation" ||
    value === "creative"
  ) {
    return value;
  }
  return null;
}

function objectiveSuffix(objective: string): string {
  return objective.length > 0 ? `\nObjective focus: ${objective}` : "";
}

export function listDirectiveBindings(): DirectiveBinding[] {
  return [...BINDINGS];
}

export function isDirectiveEventType(type: string): type is DirectiveEventType {
  return BINDINGS.some((binding) => binding.directive === type);
}

export function buildDirectiveRelayCommand(event: EventLogEntry<DirectiveEventType>): string {
  const objective = asObjective(event.payload);
  const suffix = objectiveSuffix(objective);

  switch (event.type) {
    case "DAILY_SYNC":
      return [
        "Run a DAILY_SYNC cycle for Cory now.",
        "Actions:",
        "1) Run `openclaw agents list --bindings` and `openclaw models status`.",
        "2) Check cohesion/drift across ORION, ATLAS, NODE, PULSE, STRATUS.",
        "3) If drift exists, create a concrete ATLAS task packet to repair it.",
        "4) Return a concise status report with concrete next actions.",
        "5) Label any unfinished work as pending verification.",
        suffix
      ]
        .filter(Boolean)
        .join("\n");
    case "RUN_DIAGNOSTICS":
      return [
        "Run ORION diagnostics sweep for this workspace now.",
        "Actions:",
        "1) Execute `openclaw doctor --repair` and `openclaw channels status --probe`.",
        "2) If update/install is needed, execute `openclaw gateway install` and verify.",
        "3) Summarize failures or warnings and propose top fixes in priority order.",
        "4) Confirm what is verified versus pending.",
        suffix
      ]
        .filter(Boolean)
        .join("\n");
    case "FLUSH_CACHE":
      return [
        "Run a safe FLUSH_CACHE style cleanup now.",
        "Actions:",
        "1) Identify stale context, stale queues, and outdated assumptions.",
        "2) Apply only reversible cleanups (no destructive deletes).",
        "3) Re-check health with `openclaw channels status --probe`.",
        "4) Report exactly what was cleared and what remains.",
        suffix
      ]
        .filter(Boolean)
        .join("\n");
    case "INJECT_TASK_PACKET": {
      const taskType = asTaskType(event.payload) ?? "research";
      return [
        `Create and execute a TASK_PACKET v1 of type ${taskType}.`,
        "Actions:",
        "1) Route to the right specialist owner.",
        "2) Keep the scope concrete, actionable, and verifiable.",
        "3) Sync with adjacent agents if dependencies exist.",
        "4) Return a short progress summary and next checkpoint.",
        suffix
      ]
        .filter(Boolean)
        .join("\n");
    }
    default:
      return "";
  }
}

export function objectiveFromDirectivePayload(payload: OrionEventPayloadMap[DirectiveEventType]): string | null {
  const objective = asObjective(payload);
  return objective.length > 0 ? objective : null;
}
