import path from "node:path";
import { randomUUID } from "node:crypto";
import { createRequire } from "node:module";
import { buildDirectiveRelayCommand, listDirectiveBindings, objectiveFromDirectivePayload } from "./directives";
import { PATCHES } from "./patches";
import { replay } from "./reducer";
import { buildSeedEvents } from "./seeds";
import { toTzDateString } from "./time";
import type {
  DirectiveActionRun,
  DirectiveActionStatus,
  DirectiveEventType,
  EventInput,
  EventLogEntry,
  OrionEventPayloadMap,
  OrionEventType,
  OrionSnapshot,
  PatchId
} from "./types";

const defaultPath = path.resolve(process.cwd(), "..", "db", "orion-core.sqlite");
const dbPath = process.env.ORION_CORE_DB_PATH ?? defaultPath;
if (!dbPath || typeof dbPath !== "string") {
  throw new Error(`Invalid ORION Core DB path: ${String(dbPath)}`);
}

const require = createRequire(import.meta.url);
const BetterSqlite3 = require("better-sqlite3") as
  | ((file: string) => unknown)
  | { default?: (file: string) => unknown };
const DatabaseCtor =
  typeof BetterSqlite3 === "function"
    ? BetterSqlite3
    : typeof BetterSqlite3.default === "function"
      ? BetterSqlite3.default
      : null;

if (!DatabaseCtor) {
  throw new Error("Failed to load better-sqlite3 constructor");
}

const db = ((DatabaseCtor as unknown) as (file: string) => {
  pragma: (source: string) => unknown;
  exec: (source: string) => unknown;
  prepare: (source: string) => {
    run: (...params: unknown[]) => { lastInsertRowid: number | bigint };
    get: (...params: unknown[]) => unknown;
    all: (...params: unknown[]) => unknown[];
  };
  transaction: <T extends (...args: never[]) => unknown>(fn: T) => T;
})(dbPath);
db.pragma("journal_mode = WAL");

function ensureSchema(): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      type TEXT NOT NULL,
      payload TEXT NOT NULL,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS meta (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS directive_action_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_id INTEGER NOT NULL,
      directive_type TEXT NOT NULL,
      objective TEXT,
      status TEXT NOT NULL,
      command_text TEXT,
      deliver_target TEXT,
      relay_worker_id TEXT,
      lease_until TEXT,
      claim_token TEXT,
      response_text TEXT,
      error TEXT,
      code INTEGER,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (event_id) REFERENCES events(id)
    );

    CREATE INDEX IF NOT EXISTS idx_directive_action_runs_status_created
      ON directive_action_runs(status, datetime(created_at), id);
  `);

  const directiveColumns = db.prepare("PRAGMA table_info(directive_action_runs)").all() as Array<{ name: string }>;
  const directiveColumnNames = new Set(directiveColumns.map((row) => row.name));
  if (!directiveColumnNames.has("lease_until")) {
    db.exec("ALTER TABLE directive_action_runs ADD COLUMN lease_until TEXT");
  }
  if (!directiveColumnNames.has("claim_token")) {
    db.exec("ALTER TABLE directive_action_runs ADD COLUMN claim_token TEXT");
  }
}

function insertSeedData(): void {
  const count = db.prepare("SELECT COUNT(*) as count FROM events").get() as { count: number };
  if (count.count > 0) {
    return;
  }

  const insert = db.prepare("INSERT INTO events(type, payload, created_at) VALUES (?, ?, ?)");
  const entries = buildSeedEvents();

  const txn = db.transaction(() => {
    for (const entry of entries) {
      insert.run(entry.type, JSON.stringify(entry.payload), entry.createdAt ?? new Date().toISOString());
    }
  });

  txn();
}

export function initDb(): void {
  ensureSchema();
  insertSeedData();
}

function listEventsAsc(): EventLogEntry[] {
  const rows = db
    .prepare("SELECT id, type, payload, created_at FROM events ORDER BY datetime(created_at) ASC, id ASC")
    .all() as Array<{ id: number; type: OrionEventType; payload: string; created_at: string }>;

  return rows.map((row) => ({
    id: row.id,
    type: row.type,
    payload: JSON.parse(row.payload),
    createdAt: row.created_at
  }));
}

export function listEventsDesc(limit = 150): EventLogEntry[] {
  const rows = db
    .prepare("SELECT id, type, payload, created_at FROM events ORDER BY datetime(created_at) DESC, id DESC LIMIT ?")
    .all(limit) as Array<{ id: number; type: OrionEventType; payload: string; created_at: string }>;

  return rows.map((row) => ({
    id: row.id,
    type: row.type,
    payload: JSON.parse(row.payload),
    createdAt: row.created_at
  }));
}

function appendEventInternal<T extends OrionEventType>(input: EventInput<T>): EventLogEntry<T> {
  const createdAt = input.createdAt ?? new Date().toISOString();
  const stmt = db.prepare("INSERT INTO events(type, payload, created_at) VALUES (?, ?, ?)");
  const result = stmt.run(input.type, JSON.stringify(input.payload), createdAt);

  return {
    id: Number(result.lastInsertRowid),
    type: input.type,
    payload: input.payload,
    createdAt
  };
}

export function appendEvent<T extends OrionEventType>(input: EventInput<T>): EventLogEntry<T> {
  initDb();
  ensureDailyCheck();
  return appendEventInternal(input);
}

function normalizeDeliverTarget(raw: string | null | undefined): string | null {
  if (!raw) {
    return null;
  }
  const value = String(raw).trim();
  return /^[0-9]+$/.test(value) ? value : null;
}

function resolveDeliverTarget(raw: string | null | undefined): string | null {
  const explicit = normalizeDeliverTarget(raw);
  if (explicit) {
    return explicit;
  }

  return (
    normalizeDeliverTarget(process.env.ORION_CORE_TELEGRAM_TARGET) ??
    normalizeDeliverTarget(process.env.ORION_TELEGRAM_CHAT_ID) ??
    null
  );
}

function normalizeActionStatus(raw: string): DirectiveActionStatus {
  if (raw === "queued" || raw === "claimed" || raw === "completed" || raw === "failed" || raw === "skipped") {
    return raw;
  }
  return "failed";
}

type DirectiveActionRunRow = {
  id: number;
  event_id: number;
  directive_type: DirectiveEventType;
  objective: string | null;
  status: string;
  command_text: string | null;
  deliver_target: string | null;
  relay_worker_id: string | null;
  lease_until: string | null;
  claim_token: string | null;
  response_text: string | null;
  error: string | null;
  code: number | null;
  created_at: string;
  updated_at: string;
};

function mapDirectiveActionRun(row: DirectiveActionRunRow): DirectiveActionRun {
  return {
    id: String(row.id),
    eventId: row.event_id,
    directive: row.directive_type,
    objective: row.objective,
    status: normalizeActionStatus(row.status),
    commandText: row.command_text,
    deliverTarget: row.deliver_target,
    relayWorkerId: row.relay_worker_id,
    leaseUntil: row.lease_until,
    claimToken: row.claim_token,
    responseText: row.response_text,
    error: row.error,
    code: row.code,
    createdAt: row.created_at,
    updatedAt: row.updated_at
  };
}

function getDirectiveActionRunById(id: string): DirectiveActionRun | null {
  const row = db
    .prepare(
      `
        SELECT
          id,
          event_id,
          directive_type,
          objective,
          status,
          command_text,
          deliver_target,
          relay_worker_id,
          lease_until,
          claim_token,
          response_text,
          error,
          code,
          created_at,
          updated_at
        FROM directive_action_runs
        WHERE id = ?
      `
    )
    .get(Number(id)) as DirectiveActionRunRow | undefined;

  return row ? mapDirectiveActionRun(row) : null;
}

export function listRecentDirectiveActions(limit = 30): DirectiveActionRun[] {
  initDb();
  const rows = db
    .prepare(
      `
        SELECT
          id,
          event_id,
          directive_type,
          objective,
          status,
          command_text,
          deliver_target,
          relay_worker_id,
          lease_until,
          claim_token,
          response_text,
          error,
          code,
          created_at,
          updated_at
        FROM directive_action_runs
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
      `
    )
    .all(limit) as DirectiveActionRunRow[];

  return rows.map(mapDirectiveActionRun);
}

export function queueDirectiveAction(event: EventLogEntry<DirectiveEventType>, deliverTargetRaw?: string | null): DirectiveActionRun {
  initDb();
  const now = new Date().toISOString();
  const commandText = buildDirectiveRelayCommand(event).trim() || null;
  const objective = objectiveFromDirectivePayload(event.payload);
  const deliverTarget = resolveDeliverTarget(deliverTargetRaw);

  let status: DirectiveActionStatus = "queued";
  let error: string | null = null;

  if (!commandText) {
    status = "skipped";
    error = "No executable command mapped for this directive.";
  } else if (!deliverTarget) {
    status = "skipped";
    error = "Missing Telegram delivery target for relay execution.";
  }

  const result = db
    .prepare(
      `
        INSERT INTO directive_action_runs(
          event_id,
          directive_type,
          objective,
          status,
          command_text,
          deliver_target,
          relay_worker_id,
          lease_until,
          claim_token,
          response_text,
          error,
          code,
          created_at,
          updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, NULL, ?, ?)
      `
    )
    .run(event.id, event.type, objective, status, commandText, deliverTarget, error, now, now);

  const id = String(result.lastInsertRowid);
  const run = getDirectiveActionRunById(id);
  if (!run) {
    throw new Error(`Failed to load queued directive action run ${id}`);
  }

  return run;
}

function futureIso(msFromNow: number): string {
  return new Date(Date.now() + msFromNow).toISOString();
}

export function claimDirectiveAction(workerIdRaw: string, leaseMs = 60_000): DirectiveActionRun | null {
  initDb();
  const workerId = (workerIdRaw || "relay-worker").trim() || "relay-worker";
  const claimOnce = db.transaction(() => {
    const row = db
      .prepare(
        `
          SELECT id
          FROM directive_action_runs
          WHERE status = 'queued'
          ORDER BY datetime(created_at) ASC, id ASC
          LIMIT 1
        `
      )
      .get() as { id: number } | undefined;

    if (!row) {
      return null;
    }

    const now = new Date().toISOString();
    const leaseUntil = futureIso(Math.max(5_000, Math.trunc(leaseMs)));
    const claimToken = randomUUID();
    const result = db
      .prepare(
        `
          UPDATE directive_action_runs
          SET status = 'claimed', relay_worker_id = ?, lease_until = ?, claim_token = ?, updated_at = ?
          WHERE id = ? AND status = 'queued'
        `
      )
      .run(workerId, leaseUntil, claimToken, now, row.id) as { changes?: number };

    return result.changes === 1 ? row.id : null;
  });

  while (true) {
    const claimedId = claimOnce();
    if (claimedId == null) {
      return null;
    }
    const claimed = getDirectiveActionRunById(String(claimedId));
    if (claimed) {
      return claimed;
    }
  }
}

export function completeDirectiveAction(
  id: string,
  workerIdRaw: string,
  claimTokenRaw: string,
  result: { ok: boolean; code?: number | null; responseText?: string | null; error?: string | null }
): DirectiveActionRun | null {
  initDb();
  const numericId = Number(id);
  if (!Number.isFinite(numericId) || numericId <= 0) {
    return null;
  }
  const workerId = String(workerIdRaw || "").trim();
  const claimToken = String(claimTokenRaw || "").trim();
  if (!workerId || !claimToken) {
    return null;
  }

  const status: DirectiveActionStatus = result.ok ? "completed" : "failed";
  const current = getDirectiveActionRunById(String(numericId));
  if (!current || current.status !== "claimed" || current.relayWorkerId !== workerId || current.claimToken !== claimToken) {
    return null;
  }
  if (!current.leaseUntil || Date.parse(current.leaseUntil) < Date.now()) {
    db.prepare(
      `
        UPDATE directive_action_runs
        SET status = 'failed', error = ?, lease_until = NULL, claim_token = NULL, updated_at = ?
        WHERE id = ? AND status = 'claimed'
      `
    ).run("Relay lease expired before completion.", new Date().toISOString(), numericId);
    return getDirectiveActionRunById(String(numericId));
  }

  db.prepare(
    `
      UPDATE directive_action_runs
      SET status = ?, code = ?, response_text = ?, error = ?, lease_until = NULL, claim_token = NULL, updated_at = ?
      WHERE id = ? AND status = 'claimed' AND relay_worker_id = ? AND claim_token = ?
    `
  ).run(
    status,
    typeof result.code === "number" ? Math.trunc(result.code) : null,
    result.responseText ? String(result.responseText).trim() : null,
    result.error ? String(result.error).trim() : null,
    new Date().toISOString(),
    numericId,
    workerId,
    claimToken
  );

  return getDirectiveActionRunById(String(numericId));
}

function hasMissedEventForDate(date: string): boolean {
  const rows = db
    .prepare("SELECT payload FROM events WHERE type = 'DAILY_MISSED' ORDER BY datetime(created_at) DESC LIMIT 20")
    .all() as Array<{ payload: string }>;

  return rows.some((row) => {
    const parsed = JSON.parse(row.payload) as { missedDate?: string };
    return parsed.missedDate === date;
  });
}

function latestSyncDate(): string | null {
  const row = db
    .prepare("SELECT created_at FROM events WHERE type = 'DAILY_SYNC' ORDER BY datetime(created_at) DESC, id DESC LIMIT 1")
    .get() as { created_at?: string } | undefined;

  if (!row?.created_at) {
    return null;
  }

  return toTzDateString(row.created_at);
}

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

export function ensureDailyCheck(): void {
  initDb();
  const syncDate = latestSyncDate();
  if (!syncDate) {
    return;
  }

  const today = toTzDateString(new Date());
  const diff = dateDiffDays(syncDate, today);
  if (diff <= 1) {
    return;
  }

  const missedDate = minusDays(today, 1);
  if (hasMissedEventForDate(missedDate)) {
    return;
  }

  appendEventInternal({ type: "DAILY_MISSED", payload: { missedDate } });
}

export function getSnapshot(): OrionSnapshot {
  initDb();
  ensureDailyCheck();

  const allEvents = listEventsAsc();
  const computed = replay(allEvents);
  const {
    state,
    derived,
    hasSyncedToday,
    recommendedDirective,
    dailyQuest,
    achievements,
    recoveryProtocol,
    weeklyReportCard
  } = computed;

  const patches = PATCHES.map((patch) => ({
    ...patch,
    applied: state.appliedPatches.includes(patch.id as PatchId)
  }));

  return {
    state,
    derived,
    hasSyncedToday,
    recommendedDirective,
    directiveBindings: listDirectiveBindings(),
    recentDirectiveActions: listRecentDirectiveActions(24),
    dailyQuest,
    achievements,
    recoveryProtocol,
    weeklyReportCard,
    events: listEventsDesc(120),
    patches
  };
}

export function updateSetting<K extends OrionEventPayloadMap["SETTINGS_CHANGED"]["key"]>(
  key: K,
  value: OrionEventPayloadMap["SETTINGS_CHANGED"]["value"]
): EventLogEntry<"SETTINGS_CHANGED"> {
  return appendEvent({ type: "SETTINGS_CHANGED", payload: { key, value } });
}
