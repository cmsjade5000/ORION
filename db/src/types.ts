export const TASK_PACKET_TYPES = [
  "research",
  "refactor",
  "report",
  "triage",
  "automation",
  "creative"
] as const;

export const SIMULATION_DRILL_TYPES = [
  "prompt_discipline",
  "tool_sanity",
  "summary_clarity",
  "risk_check",
  "persona_lock"
] as const;

export type TaskPacketType = (typeof TASK_PACKET_TYPES)[number];
export type SimulationDrillType = (typeof SIMULATION_DRILL_TYPES)[number];

export type OrionEventType =
  | "DAILY_SYNC"
  | "INJECT_TASK_PACKET"
  | "RUN_DIAGNOSTICS"
  | "FLUSH_CACHE"
  | "SIMULATION_RUN"
  | "TASK_CREATED"
  | "TASK_STARTED"
  | "TASK_COMPLETED"
  | "PATCH_APPLIED"
  | "NOTE_ADDED"
  | "SETTINGS_CHANGED"
  | "DAILY_MISSED";

export type RiskLevel = "low" | "balanced" | "high";
export type NotificationStyle = "standard" | "minimal" | "verbose";

export interface OrionEventPayloadMap {
  DAILY_SYNC: { objective?: string };
  INJECT_TASK_PACKET: { type: TaskPacketType; objective?: string };
  RUN_DIAGNOSTICS: { objective?: string };
  FLUSH_CACHE: { objective?: string };
  SIMULATION_RUN: { drillType: SimulationDrillType; result: "pass" | "fail" };
  TASK_CREATED: { id: string; title: string; taskType: TaskPacketType };
  TASK_STARTED: { id: string };
  TASK_COMPLETED: { id: string; outcome: "success" | "failed" | "partial" };
  PATCH_APPLIED: { patchId: PatchId };
  NOTE_ADDED: { text: string };
  SETTINGS_CHANGED: {
    key: "notificationStyle" | "riskLevel" | "piMode";
    value: string | boolean;
  };
  DAILY_MISSED: { missedDate: string };
}

export interface EventLogEntry<T extends OrionEventType = OrionEventType> {
  id: number;
  type: T;
  payload: OrionEventPayloadMap[T];
  createdAt: string;
}

export type EventInput<T extends OrionEventType = OrionEventType> = {
  type: T;
  payload: OrionEventPayloadMap[T];
  createdAt?: string;
};

export interface TaskState {
  id: string;
  title: string;
  taskType: TaskPacketType;
  status: "created" | "started" | "completed";
  outcome?: "success" | "failed" | "partial";
}

export interface OrionState {
  energy: number;
  clarity: number;
  alignment: number;
  curiosity: number;
  stability: number;
  uptime_days: number;
  last_sync_date: string | null;
  appliedPatches: PatchId[];
  tasks: Record<string, TaskState>;
  settings: {
    notificationStyle: NotificationStyle;
    riskLevel: RiskLevel;
    piMode: boolean;
  };
}

export type PatchId =
  | "focus-firmware-v1-2"
  | "stability-patch"
  | "alignment-module"
  | "curiosity-scanner"
  | "cache-optimizer"
  | "throughput-multiplier";

export interface PatchDefinition {
  id: PatchId;
  name: string;
  description: string;
}

export interface MoodDefinition {
  key:
    | "signal-noise"
    | "overclocked"
    | "low-bandwidth"
    | "scan-mode"
    | "desynced"
    | "process-locked"
    | "stable-sync"
    | "peak-throughput"
    | "background-cycle"
    | "standby";
  label:
    | "Signal Noise"
    | "Overclocked"
    | "Low Bandwidth"
    | "Scan Mode"
    | "Desynced"
    | "Process Locked"
    | "Stable Sync"
    | "Peak Throughput"
    | "Background Cycle"
    | "Standby";
  tagline: string;
}

export interface DerivedMetrics {
  signalIntegrity: number;
  coreTemperature: number;
  activeTasks: number;
  mood: MoodDefinition;
  progression: ProgressionState;
}

export type DirectiveEventType = "DAILY_SYNC" | "RUN_DIAGNOSTICS" | "FLUSH_CACHE" | "INJECT_TASK_PACKET";
export type DirectiveActionStatus = "queued" | "claimed" | "completed" | "failed" | "skipped";

export interface DirectiveBinding {
  directive: DirectiveEventType;
  label: string;
  objectiveHint: string;
  actionSummary: string;
}

export interface DirectiveActionRun {
  id: string;
  eventId: number;
  directive: DirectiveEventType;
  objective: string | null;
  status: DirectiveActionStatus;
  commandText: string | null;
  deliverTarget: string | null;
  relayWorkerId: string | null;
  leaseUntil: string | null;
  claimToken: string | null;
  responseText: string | null;
  error: string | null;
  code: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface ProgressionState {
  totalXp: number;
  level: number;
  xpIntoLevel: number;
  xpToNextLevel: number;
}

export type AchievementId =
  | "first-sync"
  | "task-closed"
  | "steady-notes"
  | "sync-streak-3"
  | "xp-100";

export interface AchievementUnlock {
  id: AchievementId;
  title: string;
  description: string;
  unlockedAt: string;
}

export interface DailyQuestStatus {
  date: string;
  recommendedDirective: DirectiveEventType;
  completed: boolean;
  requirements: {
    synced: boolean;
    followedRecommendedDirective: boolean;
    addedNote: boolean;
  };
}

export interface RecoveryProtocolMetadata {
  active: boolean;
  missedDate: string | null;
  daysSinceMissed: number | null;
}

export interface WeeklyReportCardSummary {
  windowStart: string;
  windowEnd: string;
  totalEvents: number;
  syncCount: number;
  directiveCount: number;
  noteCount: number;
  tasksCompleted: number;
  successfulTasks: number;
  missedDays: number;
  xpEarned: number;
  questDaysCompleted: number;
  achievementsUnlocked: number;
}

export interface OrionSnapshot {
  state: OrionState;
  derived: DerivedMetrics;
  hasSyncedToday: boolean;
  recommendedDirective: DirectiveEventType;
  directiveBindings: DirectiveBinding[];
  recentDirectiveActions: DirectiveActionRun[];
  dailyQuest: DailyQuestStatus;
  achievements: AchievementUnlock[];
  recoveryProtocol: RecoveryProtocolMetadata;
  weeklyReportCard: WeeklyReportCardSummary;
  events: EventLogEntry[];
  patches: Array<PatchDefinition & { applied: boolean }>;
}
