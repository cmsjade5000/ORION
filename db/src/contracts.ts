import type {
  EventInput,
  OrionEventPayloadMap,
  OrionEventType,
  SimulationDrillType,
  TaskPacketType
} from "./types";

const TASK_PACKET_TYPES = new Set<TaskPacketType>([
  "research",
  "refactor",
  "report",
  "triage",
  "automation",
  "creative"
]);

const SIMULATION_DRILL_TYPES = new Set<SimulationDrillType>([
  "prompt_discipline",
  "tool_sanity",
  "summary_clarity",
  "risk_check",
  "persona_lock"
]);

const DIRECTIVE_EVENT_TYPES = new Set<OrionEventType>([
  "DAILY_SYNC",
  "INJECT_TASK_PACKET",
  "RUN_DIAGNOSTICS",
  "FLUSH_CACHE"
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asOptionalTrimmedString(value: unknown): string | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function asNullableTrimmedString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function asBoolean(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") {
    throw new Error(`Invalid ${label}`);
  }
  return value;
}

function asInteger(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`Invalid ${label}`);
  }
  return Math.trunc(value);
}

function validateObjectiveOnlyPayload(payload: unknown, label: string): { objective?: string } {
  if (!isRecord(payload)) {
    throw new Error(`Invalid ${label} payload`);
  }
  const objective = asOptionalTrimmedString(payload.objective);
  return objective ? { objective } : {};
}

function validateInjectTaskPacketPayload(payload: unknown): OrionEventPayloadMap["INJECT_TASK_PACKET"] {
  if (!isRecord(payload)) {
    throw new Error("Invalid INJECT_TASK_PACKET payload");
  }
  if (!TASK_PACKET_TYPES.has(payload.type as TaskPacketType)) {
    throw new Error("Invalid INJECT_TASK_PACKET type");
  }
  const objective = asOptionalTrimmedString(payload.objective);
  return objective ? { type: payload.type as TaskPacketType, objective } : { type: payload.type as TaskPacketType };
}

export function validateEventInput(input: unknown): EventInput {
  if (!isRecord(input)) {
    throw new Error("Invalid event input");
  }

  const type = input.type;
  if (typeof type !== "string") {
    throw new Error("Missing event type");
  }

  switch (type) {
    case "DAILY_SYNC":
    case "RUN_DIAGNOSTICS":
    case "FLUSH_CACHE":
      return { type, payload: validateObjectiveOnlyPayload(input.payload ?? {}, type) };
    case "INJECT_TASK_PACKET":
      return { type, payload: validateInjectTaskPacketPayload(input.payload) };
    case "SIMULATION_RUN": {
      const payload = input.payload;
      if (!isRecord(payload)) {
        throw new Error("Invalid SIMULATION_RUN payload");
      }
      if (!SIMULATION_DRILL_TYPES.has(payload.drillType as SimulationDrillType)) {
        throw new Error("Invalid SIMULATION_RUN drillType");
      }
      if (payload.result !== "pass" && payload.result !== "fail") {
        throw new Error("Invalid SIMULATION_RUN result");
      }
      return {
        type,
        payload: { drillType: payload.drillType as SimulationDrillType, result: payload.result }
      };
    }
    case "TASK_CREATED": {
      const payload = input.payload;
      if (!isRecord(payload)) {
        throw new Error("Invalid TASK_CREATED payload");
      }
      const id = asOptionalTrimmedString(payload.id);
      const title = asOptionalTrimmedString(payload.title);
      if (!id || !title || !TASK_PACKET_TYPES.has(payload.taskType as TaskPacketType)) {
        throw new Error("Invalid TASK_CREATED payload");
      }
      return { type, payload: { id, title, taskType: payload.taskType as TaskPacketType } };
    }
    case "TASK_STARTED": {
      const payload = input.payload;
      if (!isRecord(payload)) {
        throw new Error("Invalid TASK_STARTED payload");
      }
      const id = asOptionalTrimmedString(payload.id);
      if (!id) {
        throw new Error("Invalid TASK_STARTED payload");
      }
      return { type, payload: { id } };
    }
    case "TASK_COMPLETED": {
      const payload = input.payload;
      if (!isRecord(payload)) {
        throw new Error("Invalid TASK_COMPLETED payload");
      }
      const id = asOptionalTrimmedString(payload.id);
      const outcome = payload.outcome;
      if (!id || (outcome !== "success" && outcome !== "failed" && outcome !== "partial")) {
        throw new Error("Invalid TASK_COMPLETED payload");
      }
      return { type, payload: { id, outcome } };
    }
    case "PATCH_APPLIED": {
      const payload = input.payload;
      if (!isRecord(payload)) {
        throw new Error("Invalid PATCH_APPLIED payload");
      }
      const patchId = asOptionalTrimmedString(payload.patchId);
      if (!patchId) {
        throw new Error("Invalid PATCH_APPLIED payload");
      }
      return { type, payload: { patchId: patchId as OrionEventPayloadMap["PATCH_APPLIED"]["patchId"] } };
    }
    case "NOTE_ADDED": {
      const payload = input.payload;
      if (!isRecord(payload)) {
        throw new Error("Invalid NOTE_ADDED payload");
      }
      const text = asOptionalTrimmedString(payload.text);
      if (!text) {
        throw new Error("Invalid NOTE_ADDED payload");
      }
      return { type, payload: { text } };
    }
    case "SETTINGS_CHANGED": {
      const payload = input.payload;
      if (!isRecord(payload)) {
        throw new Error("Invalid SETTINGS_CHANGED payload");
      }
      const key = payload.key;
      if (key !== "notificationStyle" && key !== "riskLevel" && key !== "piMode") {
        throw new Error("Invalid SETTINGS_CHANGED key");
      }
      const value =
        key === "piMode" ? asBoolean(payload.value, "SETTINGS_CHANGED value") : asOptionalTrimmedString(payload.value);
      if (value === undefined) {
        throw new Error("Invalid SETTINGS_CHANGED value");
      }
      return { type, payload: { key, value } };
    }
    case "DAILY_MISSED": {
      const payload = input.payload;
      if (!isRecord(payload)) {
        throw new Error("Invalid DAILY_MISSED payload");
      }
      const missedDate = asOptionalTrimmedString(payload.missedDate);
      if (!missedDate) {
        throw new Error("Invalid DAILY_MISSED payload");
      }
      return { type, payload: { missedDate } };
    }
    default:
      throw new Error(`Unsupported event type: ${type}`);
  }
}

export interface RelayClaimRequest {
  workerId: string;
}

export interface RelayResultRequest {
  ok: boolean;
  code: number | null;
  responseText: string | null;
  error: string | null;
  workerId: string;
  claimToken: string;
}

export function validateRelayClaimRequest(input: unknown): RelayClaimRequest {
  if (!isRecord(input)) {
    return { workerId: "relay-worker" };
  }
  return { workerId: asOptionalTrimmedString(input.workerId) ?? "relay-worker" };
}

export function validateRelayResultRequest(input: unknown): RelayResultRequest {
  if (!isRecord(input)) {
    throw new Error("Invalid relay result payload");
  }

  const workerId = asOptionalTrimmedString(input.workerId);
  const claimToken = asOptionalTrimmedString(input.claimToken);
  if (!workerId || !claimToken) {
    throw new Error("Missing relay worker or claim token");
  }

  return {
    ok: asBoolean(input.ok, "relay result ok"),
    code: input.code == null ? null : asInteger(input.code, "relay result code"),
    responseText: asNullableTrimmedString(input.responseText),
    error: asNullableTrimmedString(input.error),
    workerId,
    claimToken
  };
}

export function isDirectiveOnlyEvent(input: EventInput): boolean {
  return DIRECTIVE_EVENT_TYPES.has(input.type);
}
