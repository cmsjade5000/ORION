import { isPatchId } from "./patches";
import { resolveMood } from "./mood";
import { toTzDateString } from "./time";
import type {
  AchievementId,
  AchievementUnlock,
  DailyQuestStatus,
  DerivedMetrics,
  DirectiveEventType,
  EventLogEntry,
  OrionEventType,
  OrionSnapshot,
  OrionState,
  PatchId,
  ProgressionState,
  RecoveryProtocolMetadata,
  WeeklyReportCardSummary
} from "./types";

const clamp = (value: number): number => Math.max(0, Math.min(100, Math.round(value)));

const emptyPayload = {};
const XP_PER_LEVEL = 50;
const WEEKLY_WINDOW_DAYS = 7;
const RECOVERY_WINDOW_DAYS = 2;
const FOLLOW_UP_DIRECTIVES: DirectiveEventType[] = ["RUN_DIAGNOSTICS", "FLUSH_CACHE", "INJECT_TASK_PACKET"];
const QUEST_DIRECTIVE_TYPES: DirectiveEventType[] = ["DAILY_SYNC", ...FOLLOW_UP_DIRECTIVES];

const EMPTY_PROGRESSION: ProgressionState = {
  totalXp: 0,
  level: 1,
  xpIntoLevel: 0,
  xpToNextLevel: XP_PER_LEVEL
};

export const INITIAL_STATE: OrionState = {
  energy: 62,
  clarity: 55,
  alignment: 58,
  curiosity: 71,
  stability: 66,
  uptime_days: 0,
  last_sync_date: null,
  appliedPatches: [],
  tasks: {},
  settings: {
    notificationStyle: "standard",
    riskLevel: "balanced",
    piMode: false
  }
};

type Delta = Partial<Pick<OrionState, "energy" | "clarity" | "alignment" | "curiosity" | "stability">>;

function dateDiffDays(fromDate: string, toDate: string): number {
  const from = new Date(`${fromDate}T00:00:00`);
  const to = new Date(`${toDate}T00:00:00`);
  return Math.round((to.getTime() - from.getTime()) / 86400000);
}

function minusDays(date: string, days: number): string {
  const d = new Date(`${date}T00:00:00`);
  d.setDate(d.getDate() - days);
  return toTzDateString(d);
}

function getEventDate(event: EventLogEntry): string {
  return toTzDateString(event.createdAt);
}

function isDateInRange(date: string, start: string, end: string): boolean {
  return date >= start && date <= end;
}

function asStringPayload(payload: unknown, key: string): string | undefined {
  if (typeof payload !== "object" || payload === null) {
    return undefined;
  }
  const value = (payload as Record<string, unknown>)[key];
  return typeof value === "string" ? value : undefined;
}

function asMissedDate(payload: unknown): string | null {
  const date = asStringPayload(payload, "missedDate");
  return date && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null;
}

function isQuestDirective(type: OrionEventType): type is DirectiveEventType {
  return QUEST_DIRECTIVE_TYPES.includes(type as DirectiveEventType);
}

function addDelta(state: OrionState, delta: Delta): OrionState {
  return {
    ...state,
    energy: clamp(state.energy + (delta.energy ?? 0)),
    clarity: clamp(state.clarity + (delta.clarity ?? 0)),
    alignment: clamp(state.alignment + (delta.alignment ?? 0)),
    curiosity: clamp(state.curiosity + (delta.curiosity ?? 0)),
    stability: clamp(state.stability + (delta.stability ?? 0))
  };
}

function hasPatch(state: OrionState, patch: PatchId): boolean {
  return state.appliedPatches.includes(patch);
}

function baseDelta(type: OrionEventType, payload: unknown): Delta {
  switch (type) {
    case "DAILY_SYNC":
      return { energy: 2, clarity: 2, alignment: 2, curiosity: 1, stability: 1 };
    case "INJECT_TASK_PACKET":
      return { energy: -1, clarity: 1, alignment: 1, curiosity: 2, stability: -1 };
    case "RUN_DIAGNOSTICS":
      return { energy: -1, clarity: 2, alignment: 1, stability: 2 };
    case "FLUSH_CACHE":
      return { energy: 1, clarity: 1, stability: 1 };
    case "SIMULATION_RUN": {
      const result = typeof payload === "object" && payload !== null ? (payload as { result?: string }).result : "fail";
      if (result === "pass") {
        return { clarity: 2, alignment: 1, curiosity: 1, stability: 1 };
      }
      return { clarity: -2, alignment: -1, curiosity: 1, stability: -2 };
    }
    case "TASK_CREATED":
      return { clarity: 1, alignment: 1, curiosity: 1 };
    case "TASK_STARTED":
      return { energy: -2, clarity: 1, stability: -1 };
    case "TASK_COMPLETED": {
      const outcome = typeof payload === "object" && payload !== null ? (payload as { outcome?: string }).outcome : "partial";
      if (outcome === "success") {
        return { energy: 1, clarity: 1, alignment: 2, stability: 1 };
      }
      if (outcome === "failed") {
        return { energy: -1, clarity: -1, alignment: -2, stability: -2 };
      }
      return { clarity: 1, alignment: 1 };
    }
    case "PATCH_APPLIED":
      return { clarity: 1, stability: 1 };
    case "NOTE_ADDED":
      return { clarity: 1, alignment: 1, curiosity: 1 };
    case "DAILY_MISSED":
      return { energy: -1, alignment: -2, stability: -3 };
    case "SETTINGS_CHANGED":
    default:
      return emptyPayload;
  }
}

function applyPatchAdjustments(state: OrionState, type: OrionEventType, delta: Delta, payload: unknown): Delta {
  const next = { ...delta };

  if (hasPatch(state, "focus-firmware-v1-2") && (type === "DAILY_SYNC" || type === "RUN_DIAGNOSTICS")) {
    next.clarity = (next.clarity ?? 0) + 1;
  }

  if (hasPatch(state, "focus-firmware-v1-2") && type === "SIMULATION_RUN") {
    const result = typeof payload === "object" && payload !== null ? (payload as { result?: string }).result : "fail";
    if (result === "fail") {
      next.clarity = Math.min(0, next.clarity ?? 0) + 1;
    }
  }

  if (hasPatch(state, "stability-patch") && ["RUN_DIAGNOSTICS", "FLUSH_CACHE"].includes(type)) {
    next.stability = (next.stability ?? 0) + 1;
  }

  if (hasPatch(state, "stability-patch") && ["TASK_STARTED", "SIMULATION_RUN", "DAILY_MISSED"].includes(type)) {
    if ((next.stability ?? 0) < 0) {
      next.stability = (next.stability ?? 0) + 1;
    }
  }

  if (hasPatch(state, "alignment-module") && ["DAILY_SYNC", "TASK_COMPLETED"].includes(type)) {
    next.alignment = (next.alignment ?? 0) + 1;
  }

  if (hasPatch(state, "curiosity-scanner") && ["INJECT_TASK_PACKET", "TASK_CREATED", "NOTE_ADDED"].includes(type)) {
    next.curiosity = (next.curiosity ?? 0) + 1;
  }

  if (hasPatch(state, "cache-optimizer") && type === "FLUSH_CACHE") {
    next.energy = (next.energy ?? 0) + 1;
    next.clarity = (next.clarity ?? 0) + 1;
    next.stability = (next.stability ?? 0) + 1;
  }

  if (hasPatch(state, "throughput-multiplier") && type === "TASK_STARTED") {
    next.energy = (next.energy ?? 0) - 1;
  }

  if (hasPatch(state, "throughput-multiplier") && type === "TASK_COMPLETED") {
    const outcome = typeof payload === "object" && payload !== null ? (payload as { outcome?: string }).outcome : "partial";
    if (outcome === "success") {
      next.energy = (next.energy ?? 0) + 1;
      next.clarity = (next.clarity ?? 0) + 1;
    }
  }

  return next;
}

function applyTaskMutation(state: OrionState, event: EventLogEntry): OrionState {
  const tasks = { ...state.tasks };
  const payload = event.payload as Record<string, unknown>;

  switch (event.type) {
    case "TASK_CREATED": {
      const id = String(payload.id ?? "");
      if (!id) {
        return state;
      }
      tasks[id] = {
        id,
        title: String(payload.title ?? "Untitled Task"),
        taskType: (payload.taskType as OrionState["tasks"][string]["taskType"]) ?? "research",
        status: "created"
      };
      return { ...state, tasks };
    }
    case "TASK_STARTED": {
      const id = String(payload.id ?? "");
      if (tasks[id]) {
        tasks[id] = { ...tasks[id], status: "started" };
      }
      return { ...state, tasks };
    }
    case "TASK_COMPLETED": {
      const id = String(payload.id ?? "");
      if (tasks[id]) {
        tasks[id] = {
          ...tasks[id],
          status: "completed",
          outcome: (payload.outcome as OrionState["tasks"][string]["outcome"]) ?? "partial"
        };
      }
      return { ...state, tasks };
    }
    default:
      return state;
  }
}

function applySettingsMutation(state: OrionState, event: EventLogEntry): OrionState {
  if (event.type !== "SETTINGS_CHANGED") {
    return state;
  }

  const payload = event.payload as { key?: string; value?: unknown };
  if (payload.key === "notificationStyle") {
    if (payload.value === "standard" || payload.value === "minimal" || payload.value === "verbose") {
      return { ...state, settings: { ...state.settings, notificationStyle: payload.value } };
    }
    return state;
  }

  if (payload.key === "riskLevel") {
    if (payload.value === "low" || payload.value === "balanced" || payload.value === "high") {
      return { ...state, settings: { ...state.settings, riskLevel: payload.value } };
    }
    return state;
  }

  if (payload.key === "piMode") {
    return { ...state, settings: { ...state.settings, piMode: Boolean(payload.value) } };
  }

  return state;
}

function applyPatchMutation(state: OrionState, event: EventLogEntry): OrionState {
  if (event.type !== "PATCH_APPLIED") {
    return state;
  }

  const patchId = String((event.payload as { patchId?: string }).patchId ?? "");
  if (!isPatchId(patchId) || state.appliedPatches.includes(patchId)) {
    return state;
  }

  return { ...state, appliedPatches: [...state.appliedPatches, patchId] };
}

function applySyncMutation(state: OrionState, event: EventLogEntry): OrionState {
  if (event.type === "DAILY_SYNC") {
    const currentDate = toTzDateString(event.createdAt);
    const lastDate = state.last_sync_date;
    if (!lastDate) {
      return { ...state, uptime_days: 1, last_sync_date: currentDate };
    }

    if (currentDate === lastDate) {
      return { ...state, last_sync_date: currentDate };
    }

    const dayDiff = dateDiffDays(lastDate, currentDate);
    if (dayDiff === 1) {
      return { ...state, uptime_days: state.uptime_days + 1, last_sync_date: currentDate };
    }

    return { ...state, uptime_days: 1, last_sync_date: currentDate };
  }

  if (event.type === "DAILY_MISSED") {
    return { ...state, uptime_days: 0 };
  }

  return state;
}

export function applyEvent(prev: OrionState, event: EventLogEntry): OrionState {
  let next = { ...prev };
  next = applyPatchMutation(next, event);
  next = applySettingsMutation(next, event);
  next = applyTaskMutation(next, event);
  next = applySyncMutation(next, event);

  const initial = baseDelta(event.type, event.payload);
  const adjusted = applyPatchAdjustments(next, event.type, initial, event.payload);
  next = addDelta(next, adjusted);

  return next;
}

export function xpForEvent(event: EventLogEntry): number {
  switch (event.type) {
    case "DAILY_SYNC":
      return 10;
    case "INJECT_TASK_PACKET":
      return 5;
    case "RUN_DIAGNOSTICS":
      return 6;
    case "FLUSH_CACHE":
      return 5;
    case "SIMULATION_RUN":
      return asStringPayload(event.payload, "result") === "pass" ? 8 : 3;
    case "TASK_CREATED":
      return 4;
    case "TASK_STARTED":
      return 2;
    case "TASK_COMPLETED": {
      const outcome = asStringPayload(event.payload, "outcome");
      if (outcome === "success") {
        return 10;
      }
      if (outcome === "partial") {
        return 6;
      }
      return 3;
    }
    case "PATCH_APPLIED":
      return 7;
    case "NOTE_ADDED":
      return 4;
    case "SETTINGS_CHANGED":
      return 1;
    case "DAILY_MISSED":
    default:
      return 0;
  }
}

export function deriveProgression(events: EventLogEntry[]): ProgressionState {
  const totalXp = events.reduce((sum, event) => sum + xpForEvent(event), 0);
  const level = Math.floor(totalXp / XP_PER_LEVEL) + 1;
  const xpIntoLevel = totalXp % XP_PER_LEVEL;
  const xpToNextLevel = XP_PER_LEVEL - xpIntoLevel;

  return {
    totalXp,
    level,
    xpIntoLevel,
    xpToNextLevel
  };
}

function deriveAchievements(events: EventLogEntry[]): AchievementUnlock[] {
  const unlocked = new Set<AchievementId>();
  const achievements: AchievementUnlock[] = [];

  let notesCount = 0;
  let totalXp = 0;
  let previousSyncDate: string | null = null;
  let syncStreak = 0;

  const unlock = (id: AchievementId, title: string, description: string, unlockedAt: string): void => {
    if (unlocked.has(id)) {
      return;
    }
    unlocked.add(id);
    achievements.push({ id, title, description, unlockedAt });
  };

  for (const event of events) {
    totalXp += xpForEvent(event);

    if (event.type === "DAILY_SYNC") {
      const syncDate = getEventDate(event);

      if (!previousSyncDate) {
        syncStreak = 1;
      } else if (syncDate === previousSyncDate) {
        syncStreak = Math.max(syncStreak, 1);
      } else if (dateDiffDays(previousSyncDate, syncDate) === 1) {
        syncStreak += 1;
      } else {
        syncStreak = 1;
      }

      if (syncDate !== previousSyncDate) {
        previousSyncDate = syncDate;
      }

      unlock("first-sync", "First Contact", "Completed the first DAILY_SYNC cycle.", event.createdAt);
      if (syncStreak >= 3) {
        unlock("sync-streak-3", "Three-Day Streak", "Maintained DAILY_SYNC across 3 consecutive days.", event.createdAt);
      }
    }

    if (event.type === "TASK_COMPLETED" && asStringPayload(event.payload, "outcome") === "success") {
      unlock("task-closed", "Task Closer", "Completed a task with a successful outcome.", event.createdAt);
    }

    if (event.type === "NOTE_ADDED") {
      notesCount += 1;
      if (notesCount >= 5) {
        unlock("steady-notes", "Steady Notes", "Logged at least 5 notes in the event history.", event.createdAt);
      }
    }

    if (totalXp >= 100) {
      unlock("xp-100", "Century XP", "Reached 100 cumulative XP.", event.createdAt);
    }
  }

  return achievements;
}

function deriveRecoveryProtocol(events: EventLogEntry[]): RecoveryProtocolMetadata {
  const today = toTzDateString(new Date());
  const missedDates = events
    .filter((event) => event.type === "DAILY_MISSED")
    .map((event) => asMissedDate(event.payload) ?? getEventDate(event))
    .sort();

  const missedDate = missedDates.length > 0 ? missedDates[missedDates.length - 1] : null;
  if (!missedDate) {
    return { active: false, missedDate: null, daysSinceMissed: null };
  }

  const daysSinceMissed = dateDiffDays(missedDate, today);
  return {
    active: daysSinceMissed >= 0 && daysSinceMissed <= RECOVERY_WINDOW_DAYS,
    missedDate,
    daysSinceMissed
  };
}

function deriveWeeklyReportCard(events: EventLogEntry[], achievements: AchievementUnlock[]): WeeklyReportCardSummary {
  const windowEnd = toTzDateString(new Date());
  const windowStart = minusDays(windowEnd, WEEKLY_WINDOW_DAYS - 1);
  const weeklyEvents = events.filter((event) => isDateInRange(getEventDate(event), windowStart, windowEnd));

  const syncCount = weeklyEvents.filter((event) => event.type === "DAILY_SYNC").length;
  const directiveCount = weeklyEvents.filter((event) =>
    event.type === "RUN_DIAGNOSTICS" || event.type === "FLUSH_CACHE" || event.type === "INJECT_TASK_PACKET"
  ).length;
  const noteCount = weeklyEvents.filter((event) => event.type === "NOTE_ADDED").length;
  const tasksCompleted = weeklyEvents.filter((event) => event.type === "TASK_COMPLETED").length;
  const successfulTasks = weeklyEvents.filter(
    (event) => event.type === "TASK_COMPLETED" && asStringPayload(event.payload, "outcome") === "success"
  ).length;
  const missedDays = weeklyEvents.filter((event) => event.type === "DAILY_MISSED").length;
  const xpEarned = weeklyEvents.reduce((sum, event) => sum + xpForEvent(event), 0);

  const daySignals = new Map<string, { synced: boolean; directive: boolean; note: boolean }>();
  for (const event of weeklyEvents) {
    const date = getEventDate(event);
    const current = daySignals.get(date) ?? { synced: false, directive: false, note: false };

    if (event.type === "DAILY_SYNC") {
      current.synced = true;
    }

    if (isQuestDirective(event.type)) {
      current.directive = true;
    }

    if (event.type === "NOTE_ADDED") {
      current.note = true;
    }

    daySignals.set(date, current);
  }

  const questDaysCompleted = Array.from(daySignals.values()).filter((day) => day.synced && day.directive && day.note).length;
  const achievementsUnlocked = achievements.filter((achievement) =>
    isDateInRange(toTzDateString(achievement.unlockedAt), windowStart, windowEnd)
  ).length;

  return {
    windowStart,
    windowEnd,
    totalEvents: weeklyEvents.length,
    syncCount,
    directiveCount,
    noteCount,
    tasksCompleted,
    successfulTasks,
    missedDays,
    xpEarned,
    questDaysCompleted,
    achievementsUnlocked
  };
}

function deriveDailyQuestStatus(
  events: EventLogEntry[],
  syncedToday: boolean,
  recommendedDirective: DirectiveEventType
): DailyQuestStatus {
  const today = toTzDateString(new Date());
  const todayEvents = events.filter((event) => getEventDate(event) === today);
  const followedRecommendedDirective = todayEvents.some((event) => event.type === recommendedDirective);
  const addedNote = todayEvents.some((event) => event.type === "NOTE_ADDED");
  const completed = syncedToday && followedRecommendedDirective && addedNote;

  return {
    date: today,
    recommendedDirective,
    completed,
    requirements: {
      synced: syncedToday,
      followedRecommendedDirective,
      addedNote
    }
  };
}

export function deriveMetrics(state: OrionState, progression: ProgressionState = EMPTY_PROGRESSION): DerivedMetrics {
  const tasks = Object.values(state.tasks);
  const activeTasks = tasks.filter((task) => task.status !== "completed").length;
  const signalIntegrity = clamp((state.stability + state.clarity + state.alignment) / 3);
  const coreTemperature = clamp((100 - state.energy) * 0.7 + activeTasks * 8 + (100 - state.stability) * 0.2);

  const mood = resolveMood({ state, signalIntegrity, coreTemperature, activeTasks });

  return {
    signalIntegrity,
    coreTemperature,
    activeTasks,
    mood,
    progression
  };
}

function hasSyncedToday(events: EventLogEntry[]): boolean {
  const today = toTzDateString(new Date());
  return events.some((event) => event.type === "DAILY_SYNC" && getEventDate(event) === today);
}

export function getRecommendedDirective(state: OrionState, derived: DerivedMetrics, syncedToday: boolean): OrionSnapshot["recommendedDirective"] {
  if (!syncedToday) {
    return "DAILY_SYNC";
  }

  if (state.settings.riskLevel === "high" && (state.alignment < 70 || derived.signalIntegrity < 70)) {
    return "RUN_DIAGNOSTICS";
  }

  if (derived.signalIntegrity < 60) {
    return "RUN_DIAGNOSTICS";
  }

  if (state.energy < 45 || derived.coreTemperature > 78) {
    return "FLUSH_CACHE";
  }

  if (derived.activeTasks === 0 || state.settings.riskLevel === "low") {
    return "INJECT_TASK_PACKET";
  }

  return "RUN_DIAGNOSTICS";
}

export function replay(events: EventLogEntry[]): OrionSnapshot {
  const state = events.reduce<OrionState>((acc, event) => applyEvent(acc, event), INITIAL_STATE);
  const progression = deriveProgression(events);
  const derived = deriveMetrics(state, progression);
  const syncedToday = hasSyncedToday(events);
  const recommendedDirective = getRecommendedDirective(state, derived, syncedToday);
  const achievements = deriveAchievements(events);
  const dailyQuest = deriveDailyQuestStatus(events, syncedToday, recommendedDirective);
  const recoveryProtocol = deriveRecoveryProtocol(events);
  const weeklyReportCard = deriveWeeklyReportCard(events, achievements);

  return {
    state,
    derived,
    hasSyncedToday: syncedToday,
    recommendedDirective,
    directiveBindings: [],
    recentDirectiveActions: [],
    dailyQuest,
    achievements,
    recoveryProtocol,
    weeklyReportCard,
    events,
    patches: []
  };
}
