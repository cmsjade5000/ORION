"use client";

import type { CSSProperties } from "react";
import type { EventLogEntry, OrionSnapshot } from "@orion-core/db";

export type OrbExpression = "joy" | "focus" | "alert" | "tired" | "sleepy" | "steady";

export function Meter({ label, value, large = false }: { label: string; value: number; large?: boolean }) {
  return (
    <div className={`meter ${large ? "meter-large" : ""}`}>
      <div className="meter-head">
        <span>{label}</span>
        <strong>{value}%</strong>
      </div>
      <div className="meter-track">
        <span className="meter-fill" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

export function SignalRing({
  value,
  piMode,
  expression,
  label
}: {
  value: number;
  piMode: boolean;
  expression: OrbExpression;
  label: string;
}) {
  const style = {
    "--signal-deg": `${value * 3.6}deg`
  } as CSSProperties;

  return (
    <div className={`signal-ring ${piMode ? "pi" : ""} expression-${expression}`} style={style} role="img" aria-label={label}>
      <div className="ring-grid" />
      <div className="signal-sweep" />
      <div className="orbit orbit-a" />
      <div className="orbit orbit-b" />
      <span className="signal-burst burst-a" />
      <span className="signal-burst burst-b" />
      <span className="signal-burst burst-c" />
      <div className="signal-inner">
        <div className="core-orb">
          <span className="core-pulse pulse-a" />
          <span className="core-pulse pulse-b" />
          <span className="core-halo" />
          <span className="orb-cheek cheek-left" />
          <span className="orb-cheek cheek-right" />
          <div className="orb-face">
            <span className="orb-brow brow-left" />
            <span className="orb-brow brow-right" />
            <span className="orb-eye eye-left">
              <span className="orb-pupil" />
            </span>
            <span className="orb-eye eye-right">
              <span className="orb-pupil" />
            </span>
            <span className="orb-mouth" />
          </div>
          <span className="core-kernel" />
        </div>
      </div>
    </div>
  );
}

export function Chip({ label, value }: { label: string; value: number }) {
  return (
    <div className="chip">
      <span>{label}</span>
      <strong>{value}%</strong>
    </div>
  );
}

export function BottomNav({
  active,
  onChange
}: {
  active: "home" | "directives" | "log";
  onChange: (tab: "home" | "directives" | "log") => void;
}) {
  return (
    <nav className="bottom-nav" aria-label="Main navigation">
      <button className={active === "home" ? "active" : ""} onClick={() => onChange("home")}>
        Home
      </button>
      <button className={active === "directives" ? "active" : ""} onClick={() => onChange("directives")}>
        Missions
      </button>
      <button className={active === "log" ? "active" : ""} onClick={() => onChange("log")}>
        Log
      </button>
    </nav>
  );
}

const EVENT_ICON: Record<string, string> = {
  DAILY_SYNC: "SYNC",
  INJECT_TASK_PACKET: "TASK",
  RUN_DIAGNOSTICS: "SCAN",
  FLUSH_CACHE: "FLUSH",
  SIMULATION_RUN: "SIM",
  TASK_CREATED: "NEW",
  TASK_STARTED: "LIVE",
  TASK_COMPLETED: "DONE",
  PATCH_APPLIED: "PATCH",
  NOTE_ADDED: "NOTE",
  SETTINGS_CHANGED: "CFG",
  DAILY_MISSED: "MISS"
};

export function EventTimeline({
  events,
  onSelect,
  selectedId
}: {
  events: OrionSnapshot["events"];
  selectedId: number | null;
  onSelect: (event: EventLogEntry) => void;
}) {
  return (
    <div className="event-list">
      {events.map((event) => (
        <button
          key={event.id}
          className={`event-row ${selectedId === event.id ? "selected" : ""}`}
          onClick={() => onSelect(event)}
        >
          <span className="event-icon">{EVENT_ICON[event.type] ?? "LOG"}</span>
          <span className="event-main">
            <strong>{event.type.replaceAll("_", " ")}</strong>
            <small>{new Date(event.createdAt).toLocaleString()}</small>
            <em>{previewPayload(event.payload)}</em>
          </span>
        </button>
      ))}
    </div>
  );
}

function previewPayload(payload: unknown): string {
  if (!payload || typeof payload !== "object") {
    return "No payload";
  }

  const entries = Object.entries(payload as Record<string, unknown>).slice(0, 2);
  if (entries.length === 0) {
    return "No payload";
  }

  return entries.map(([key, value]) => `${key}: ${String(value)}`).join(" · ");
}
