import { useEffect, useMemo, useRef, useState } from "react";
import type { AgentActivity, AgentState } from "../api/state";

type Opts = {
  // How long a new activity must remain stable before we show it.
  debounceMs?: number;
  // Idle is noisy; require it to be stable longer before switching to idle.
  idleDebounceMs?: number;
  // Minimum time to keep a non-idle activity visible once shown.
  minDisplayMs?: number;
  // Activities that should bypass most smoothing (surface immediately).
  immediate?: AgentActivity[];
};

type Entry = {
  shown: AgentActivity;
  shownAt: number;
  pending: AgentActivity | null;
  pendingAt: number;
  timer: number | null;
};

function normalize(a: AgentActivity | undefined): AgentActivity {
  return a ?? "idle";
}

/**
 * Client-side smoothing so activity badges don't jitter/flicker when the backend
 * reports rapid state changes (common with polling + short-lived tool events).
 */
export function useSmoothedActivities(agents: AgentState[], opts?: Opts) {
  const debounceMs = opts?.debounceMs ?? 240;
  const idleDebounceMs = opts?.idleDebounceMs ?? 900;
  const minDisplayMs = opts?.minDisplayMs ?? 1100;
  const immediate = opts?.immediate ?? ["error", "messaging"];

  const [shown, setShown] = useState<Record<string, AgentActivity>>({});
  const entriesRef = useRef<Record<string, Entry>>({});
  const rawRef = useRef<Record<string, AgentActivity>>({});

  useEffect(() => {
    const now = Date.now();
    const entries = entriesRef.current;

    // Update raw snapshot for timers to consult.
    for (const a of agents) rawRef.current[a.id] = normalize(a.activity);

    const clearTimer = (id: string) => {
      const e = entries[id];
      if (e?.timer) {
        window.clearTimeout(e.timer);
        e.timer = null;
      }
    };

    const switchTo = (id: string, next: AgentActivity) => {
      const e = entries[id];
      if (!e) return;
      e.shown = next;
      e.shownAt = Date.now();
      e.pending = null;
      e.pendingAt = 0;
      clearTimer(id);
      setShown((prev) => (prev[id] === next ? prev : { ...prev, [id]: next }));
    };

    const consider = (id: string, raw: AgentActivity) => {
      const e = entries[id];
      if (!e) return;

      if (raw === e.shown) {
        e.pending = null;
        e.pendingAt = 0;
        clearTimer(id);
        setShown((prev) => (prev[id] === e.shown ? prev : { ...prev, [id]: e.shown }));
        return;
      }

      if (e.pending !== raw) {
        e.pending = raw;
        e.pendingAt = Date.now();
      }

      const stableFor = Date.now() - e.pendingAt;
      const shownFor = Date.now() - e.shownAt;
      const wantIdle = raw === "idle";
      const debounce = wantIdle ? idleDebounceMs : debounceMs;
      const minHold = e.shown === "idle" ? 0 : minDisplayMs;
      const isImmediate = immediate.includes(raw);

      const canSwitch = (stableFor >= debounce && shownFor >= minHold) || isImmediate;
      if (canSwitch) return switchTo(id, raw);

      const dueAt = Math.max(e.pendingAt + debounce, e.shownAt + minHold);
      const delay = Math.max(10, dueAt - Date.now());
      clearTimer(id);
      e.timer = window.setTimeout(() => {
        const latestRaw = rawRef.current[id] ?? "idle";
        const cur = entriesRef.current[id];
        if (!cur) return;
        // Only switch if the pending activity is still the latest raw activity.
        if (cur.pending !== latestRaw) return;
        consider(id, latestRaw);
      }, delay);
    };

    // Ensure entries exist for all agents and run a decision pass.
    for (const a of agents) {
      const id = a.id;
      const raw = normalize(a.activity);
      if (!entries[id]) {
        entries[id] = {
          shown: raw,
          shownAt: now,
          pending: null,
          pendingAt: 0,
          timer: null,
        };
        setShown((prev) => (prev[id] ? prev : { ...prev, [id]: raw }));
      } else {
        consider(id, raw);
      }
    }

    // Cleanup timers for removed agents to avoid leaking timeouts.
    const live = new Set(agents.map((a) => a.id));
    for (const id of Object.keys(entries)) {
      if (!live.has(id)) {
        clearTimer(id);
        delete entries[id];
        delete rawRef.current[id];
        setShown((prev) => {
          if (!(id in prev)) return prev;
          const next = { ...prev };
          delete next[id];
          return next;
        });
      }
    }

    return () => {};
  }, [agents, debounceMs, idleDebounceMs, minDisplayMs, immediate]);

  // On unmount: clear any outstanding timers.
  useEffect(() => {
    return () => {
      const entries = entriesRef.current;
      for (const id of Object.keys(entries)) {
        const t = entries[id]?.timer;
        if (t) window.clearTimeout(t);
      }
    };
  }, []);

  return useMemo(() => shown, [shown]);
}

