"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  DirectiveEventType,
  EventLogEntry,
  OrionSnapshot,
  PatchId,
  SimulationDrillType,
  TaskPacketType
} from "@orion-core/db";
import { applyPatch, dispatchEvent, fetchSnapshot } from "@/lib/api";
import { dismissTelegramKeyboard, initTelegramWebApp, resolveWebAppUser } from "@/lib/telegram";
import { BottomNav, Chip, EventTimeline, Meter, SignalRing, type OrbExpression } from "@/components/ui";

const taskPacketTypes: TaskPacketType[] = ["research", "refactor", "report", "triage", "automation", "creative"];
const drillTypes: SimulationDrillType[] = [
  "prompt_discipline",
  "tool_sanity",
  "summary_clarity",
  "risk_check",
  "persona_lock"
];

function directiveLabel(directive: DirectiveEventType): string {
  switch (directive) {
    case "DAILY_SYNC":
      return "Daily Sync";
    case "RUN_DIAGNOSTICS":
      return "Run Diagnostics";
    case "FLUSH_CACHE":
      return "Flush Cache";
    case "INJECT_TASK_PACKET":
      return "Inject Task Packet";
    default:
      return directive;
  }
}

function actionStatusLabel(status: "queued" | "claimed" | "completed" | "failed" | "skipped"): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "claimed":
      return "In Progress";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "skipped":
      return "Skipped";
    default:
      return status;
  }
}

function recommendationReason(snapshot: OrionSnapshot): string {
  const { state, derived, hasSyncedToday } = snapshot;
  if (!hasSyncedToday) {
    return "No sync logged today. Start with Daily Sync to protect the streak meter.";
  }
  if (state.settings.riskLevel === "high" && (state.alignment < 70 || derived.signalIntegrity < 70)) {
    return "High risk profile with weak alignment. Diagnostics is the cleanest stabilizer.";
  }
  if (derived.signalIntegrity < 60) {
    return "Signal integrity dropped under the safe band. Diagnostics should come next.";
  }
  if (state.energy < 45 || derived.coreTemperature > 78) {
    return "Thermal load is creeping up. Cache flush buys recovery without losing rhythm.";
  }
  if (derived.activeTasks === 0) {
    return "The queue is quiet. Injecting a task packet keeps XP and momentum moving.";
  }
  return "Current state is stable. One extra directive keeps drift low and rewards high.";
}

function companionLine(snapshot: OrionSnapshot): string {
  const { dailyQuest, recoveryProtocol, derived } = snapshot;
  if (recoveryProtocol.active) {
    return "Recovery Protocol active. One clean cycle brings the orb back into rhythm.";
  }
  if (dailyQuest.completed) {
    return "Daily loop complete. ORION is idling in bonus-XP territory.";
  }
  if (!dailyQuest.requirements.synced) {
    return "Open with Daily Sync and lock the cycle before the day gets noisy.";
  }
  if (!dailyQuest.requirements.followedRecommendedDirective) {
    return `Next move: ${directiveLabel(dailyQuest.recommendedDirective)}.`;
  }
  if (!dailyQuest.requirements.addedNote) {
    return "Drop one system note to seal the loop and bank the day.";
  }
  return `${derived.mood.label} maintained. Push one optional mission for a cleaner board.`;
}

function resolveOrbExpression(snapshot: OrionSnapshot): OrbExpression {
  const { derived, recoveryProtocol, state } = snapshot;
  if (recoveryProtocol.active || derived.mood.key === "low-bandwidth") {
    return "sleepy";
  }
  if (derived.mood.key === "overclocked" || derived.coreTemperature > 80) {
    return "alert";
  }
  if (derived.mood.key === "desynced" || derived.signalIntegrity < 58) {
    return "tired";
  }
  if (derived.mood.key === "scan-mode" || derived.mood.key === "process-locked") {
    return "focus";
  }
  if (derived.mood.key === "peak-throughput" && state.energy >= 70) {
    return "joy";
  }
  return "steady";
}

function orbMoodLine(expression: OrbExpression): string {
  switch (expression) {
    case "joy":
      return "Orb is energized and showing off.";
    case "focus":
      return "Orb is locked in and tracking targets.";
    case "alert":
      return "Orb is hot and watching for drift.";
    case "tired":
      return "Orb is strained and wants a reset.";
    case "sleepy":
      return "Orb is conserving power to recover.";
    case "steady":
    default:
      return "Orb is stable and ready for directives.";
  }
}

function missionReward(directive: DirectiveEventType): string {
  switch (directive) {
    case "DAILY_SYNC":
      return "Streak + rhythm";
    case "RUN_DIAGNOSTICS":
      return "Clarity + stability";
    case "FLUSH_CACHE":
      return "Energy + cooldown";
    case "INJECT_TASK_PACKET":
      return "XP + fresh queue";
    default:
      return "Core boost";
  }
}

export default function Page() {
  const [tab, setTab] = useState<"home" | "directives" | "log">("home");
  const [snapshot, setSnapshot] = useState<OrionSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showMenu, setShowMenu] = useState(false);
  const [panel, setPanel] = useState<"none" | "patches" | "settings" | "inject" | "simulation">("none");
  const [selectedEvent, setSelectedEvent] = useState<EventLogEntry | null>(null);
  const [objectiveText, setObjectiveText] = useState("");

  const user = useMemo(() => resolveWebAppUser(), []);

  useEffect(() => {
    initTelegramWebApp();
    void refresh();
  }, []);

  async function refresh(): Promise<void> {
    try {
      setLoading(true);
      setError(null);
      const next = await fetchSnapshot();
      setSnapshot(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load snapshot");
    } finally {
      setLoading(false);
    }
  }

  async function runEvent<T extends Parameters<typeof dispatchEvent>[0]>(
    type: T,
    payload?: Parameters<typeof dispatchEvent>[1]
  ): Promise<void> {
    try {
      setError(null);
      const operator = user.mode === "telegram" && user.id > 0 ? { telegramUserId: user.id } : undefined;
      const next = await dispatchEvent(type, payload as never, operator);
      setSnapshot(next);
      dismissTelegramKeyboard();
      setPanel("none");
      setShowMenu(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Directive failed");
    }
  }

  async function runPatch(patchId: PatchId): Promise<void> {
    try {
      const next = await applyPatch(patchId);
      setSnapshot(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Patch apply failed");
    }
  }

  if (loading && !snapshot) {
    return <main className="shell loading">Booting ORION Mission Control...</main>;
  }

  if (!snapshot) {
    return (
      <main className="shell loading">
        <p>{error ?? "Could not load ORION Core."}</p>
        <button className="btn btn-primary" onClick={() => void refresh()}>
          Retry
        </button>
      </main>
    );
  }

  const { state, derived } = snapshot;
  const secondaryCta = snapshot.hasSyncedToday ? "RUN_DIAGNOSTICS" : "DAILY_SYNC";
  const xpProgressPct = Math.max(0, Math.min(100, Math.round((derived.progression.xpIntoLevel / 50) * 100)));
  const unlockedCount = snapshot.achievements.length;
  const recentAchievements = snapshot.achievements.slice(-3).reverse();
  const objective = objectiveText.trim();
  const orbExpression = resolveOrbExpression(snapshot);
  const readiness = Math.round((state.energy + state.clarity + state.alignment + state.stability) / 4);
  const heatClass = derived.coreTemperature >= 78 ? "warn" : derived.coreTemperature >= 65 ? "watch" : "cool";
  const objectiveHint =
    objective.length > 0 ? objective : recommendationReason(snapshot);
  const withObjective = <T extends Record<string, unknown>>(payload: T): T =>
    objective.length > 0 ? ({ ...payload, objective } as T) : payload;

  const missionCards = [
    {
      key: "DAILY_SYNC" as const,
      title: "Daily Sync",
      summary: "Recharge the core, lock the streak, and rebalance the board.",
      reward: missionReward("DAILY_SYNC"),
      tone: "sync",
      action: () => void runEvent("DAILY_SYNC", withObjective({}))
    },
    {
      key: "RUN_DIAGNOSTICS" as const,
      title: "Run Diagnostics",
      summary: "Scan routes, align specialists, and clean up unstable lanes.",
      reward: missionReward("RUN_DIAGNOSTICS"),
      tone: "diagnostics",
      action: () => void runEvent("RUN_DIAGNOSTICS", withObjective({}))
    },
    {
      key: "FLUSH_CACHE" as const,
      title: "Flush Cache",
      summary: "Cut thermal pressure and give the orb a quick recovery cycle.",
      reward: missionReward("FLUSH_CACHE"),
      tone: "flush",
      action: () => void runEvent("FLUSH_CACHE", withObjective({}))
    },
    {
      key: "INJECT_TASK_PACKET" as const,
      title: "Inject Task Packet",
      summary: "Spawn a fresh mission packet when the queue needs XP fuel.",
      reward: missionReward("INJECT_TASK_PACKET"),
      tone: "inject",
      action: () => setPanel("inject")
    },
    {
      key: "SIMULATION_RUN" as const,
      title: "Simulation Run",
      summary: "Stress-test prompt discipline, tool sanity, and persona lock.",
      reward: "Drill bonus",
      tone: "simulation",
      action: () => setPanel("simulation")
    },
    {
      key: "NOTE_ADDED" as const,
      title: "Add System Note",
      summary: "Capture context while the orb still remembers the shape of the day.",
      reward: "Memory + alignment",
      tone: "note",
      action: () => {
        const text = window.prompt("Add system note");
        if (text && text.trim().length > 0) {
          void runEvent("NOTE_ADDED", { text: text.trim() });
        }
      }
    }
  ];

  return (
    <main className={`shell ${state.settings.piMode ? "pi-mode" : ""}`}>
      <div className="shell-glow shell-glow-a" />
      <div className="shell-glow shell-glow-b" />

      <header className="topbar">
        <div>
          <small>{user.mode === "telegram" ? `@${user.username}` : "Local Mode"}</small>
          <h1>ORION Mission Control</h1>
        </div>
        {tab === "home" && (
          <button className="menu-btn" onClick={() => setShowMenu((prev) => !prev)} aria-label="Open home menu">
            Loadout
          </button>
        )}
      </header>

      {showMenu && tab === "home" && (
        <div className="menu-sheet">
          <button onClick={() => setPanel("patches")}>Patch Bay</button>
          <button onClick={() => setPanel("settings")}>Settings</button>
        </div>
      )}

      {tab === "home" && (
        <section className="view home-view">
          <section className="card hero-card">
            <div className="hero-copy">
              <span className="eyebrow">Live Orb</span>
              <div className="hero-title-row">
                <div>
                  <h2>{derived.mood.label}</h2>
                  <p>{derived.mood.tagline}</p>
                </div>
                <span className={`hero-state hero-state-${orbExpression}`}>{orbMoodLine(orbExpression)}</span>
              </div>
              <small className="companion-line">{companionLine(snapshot)}</small>
              <div className="hero-stats">
                <article className="mini-stat">
                  <span>Uptime</span>
                  <strong>{state.uptime_days}d</strong>
                </article>
                <article className="mini-stat">
                  <span>Queue</span>
                  <strong>{derived.activeTasks}</strong>
                </article>
                <article className="mini-stat">
                  <span>Readiness</span>
                  <strong>{readiness}%</strong>
                </article>
              </div>
            </div>
            <div className="hero-orb-column">
              <SignalRing
                value={derived.signalIntegrity}
                piMode={state.settings.piMode}
                expression={orbExpression}
                label={`${derived.mood.label}: ${orbMoodLine(orbExpression)}`}
              />
              <div className="orb-caption">
                <strong>Core L{derived.progression.level}</strong>
                <small>{orbMoodLine(orbExpression)}</small>
              </div>
            </div>
          </section>

          <section className="hero-grid">
            <article className="card spotlight-card">
              <div className="spotlight-head">
                <div>
                  <span className="eyebrow">Recommended Mission</span>
                  <strong>{directiveLabel(snapshot.recommendedDirective)}</strong>
                </div>
                <span className={`heat-badge ${heatClass}`}>Heat {derived.coreTemperature}%</span>
              </div>
              <p>{objectiveHint}</p>
              <div className="spotlight-actions">
                <button
                  className="btn btn-primary"
                  onClick={() =>
                    void runEvent(
                      snapshot.recommendedDirective,
                      snapshot.recommendedDirective === "INJECT_TASK_PACKET"
                        ? withObjective({ type: "research" })
                        : withObjective({})
                    )
                  }
                >
                  Run Recommended Directive
                </button>
                <button className="btn btn-secondary" onClick={() => void runEvent(secondaryCta, withObjective({}))}>
                  {secondaryCta === "DAILY_SYNC" ? "Daily Sync" : "Run Diagnostics"}
                </button>
              </div>
            </article>

            <article className="card progression-card">
              <div className="progression-head">
                <div>
                  <span className="eyebrow">Progression</span>
                  <strong>L{derived.progression.level}</strong>
                </div>
                <div className="progression-meta">
                  <small>Total XP</small>
                  <strong>{derived.progression.totalXp}</strong>
                </div>
              </div>
              <div className="xp-track" aria-label="XP progress">
                <span className="xp-fill" style={{ width: `${xpProgressPct}%` }} />
              </div>
              <div className="progression-foot">
                <small>
                  {derived.progression.xpIntoLevel}/{derived.progression.xpIntoLevel + derived.progression.xpToNextLevel} XP this level
                </small>
                <small>{derived.progression.xpToNextLevel} XP to next level</small>
              </div>
              <div className="badge-row">
                <span className="badge-pill">Signal {derived.signalIntegrity}%</span>
                <span className="badge-pill">Risk {state.settings.riskLevel}</span>
                <span className="badge-pill">{snapshot.hasSyncedToday ? "Synced today" : "Sync pending"}</span>
              </div>
            </article>
          </section>

          <section className="card status-board">
            <div className="section-head">
              <div>
                <span className="eyebrow">Core Stats</span>
                <strong>Color lanes</strong>
              </div>
              <small>{recommendationReason(snapshot)}</small>
            </div>
            <div className="meters-grid">
              <Meter label="Energy" value={state.energy} large />
              <Meter label="Stability" value={state.stability} large />
            </div>
            <div className="chip-grid">
              <Chip label="Clarity" value={state.clarity} />
              <Chip label="Alignment" value={state.alignment} />
              <Chip label="Curiosity" value={state.curiosity} />
            </div>
          </section>

          <section className="card quest-card">
            <div className="section-head">
              <div>
                <span className="eyebrow">Daily Loop</span>
                <strong>Today&apos;s Objective</strong>
              </div>
              <span className={`quest-status ${snapshot.dailyQuest.completed ? "done" : "open"}`}>
                {snapshot.dailyQuest.completed ? "Cycle Complete" : "In Progress"}
              </span>
            </div>
            <p>
              Complete the loop: sync, run <strong>{directiveLabel(snapshot.dailyQuest.recommendedDirective)}</strong>, and add a note.
            </p>
            <div className="quest-list">
              <span className={snapshot.dailyQuest.requirements.synced ? "done" : ""}>
                {snapshot.dailyQuest.requirements.synced ? "Done" : "Open"} · Daily Sync
              </span>
              <span className={snapshot.dailyQuest.requirements.followedRecommendedDirective ? "done" : ""}>
                {snapshot.dailyQuest.requirements.followedRecommendedDirective ? "Done" : "Open"} · Recommended Directive
              </span>
              <span className={snapshot.dailyQuest.requirements.addedNote ? "done" : ""}>
                {snapshot.dailyQuest.requirements.addedNote ? "Done" : "Open"} · Add System Note
              </span>
            </div>
          </section>

          <section className="card mission-preview-card">
            <div className="section-head">
              <div>
                <span className="eyebrow">Quick Launch</span>
                <strong>Mission deck</strong>
              </div>
              <small>Tap into Missions for full loadout</small>
            </div>
            <div className="mission-preview-grid">
              {missionCards.slice(0, 4).map((mission) => (
                <button key={mission.key} className={`mini-mission ${mission.tone}`} onClick={mission.action}>
                  <strong>{mission.title}</strong>
                  <small>{mission.reward}</small>
                </button>
              ))}
            </div>
          </section>

          {snapshot.recoveryProtocol.active && (
            <section className="card recovery-card">
              <span className="eyebrow">Recovery Protocol</span>
              <strong>Missed sync detected</strong>
              <p>
                Missed sync on {snapshot.recoveryProtocol.missedDate}. Run one clean cycle today to recover momentum.
              </p>
            </section>
          )}

          <section className="split-grid">
            <section className="card achievements-card">
              <div className="section-head">
                <div>
                  <span className="eyebrow">Rewards</span>
                  <strong>Milestones</strong>
                </div>
                <small>{unlockedCount} unlocked</small>
              </div>
              {recentAchievements.length === 0 && (
                <p className="achievements-empty">No milestones unlocked yet. Clear today&apos;s cycle to start the board.</p>
              )}
              {recentAchievements.map((achievement) => (
                <div key={achievement.id} className="achievement-item">
                  <strong>{achievement.title}</strong>
                  <small>{achievement.description}</small>
                </div>
              ))}
            </section>

            <section className="card weekly-card">
              <div className="section-head">
                <div>
                  <span className="eyebrow">Weekly Board</span>
                  <strong>Report card</strong>
                </div>
                <small>
                  {snapshot.weeklyReportCard.windowStart} to {snapshot.weeklyReportCard.windowEnd}
                </small>
              </div>
              <div className="weekly-grid">
                <span>Events: {snapshot.weeklyReportCard.totalEvents}</span>
                <span>Syncs: {snapshot.weeklyReportCard.syncCount}</span>
                <span>Quest Days: {snapshot.weeklyReportCard.questDaysCompleted}</span>
                <span>Tasks Closed: {snapshot.weeklyReportCard.tasksCompleted}</span>
                <span>Missed Days: {snapshot.weeklyReportCard.missedDays}</span>
                <span>XP: +{snapshot.weeklyReportCard.xpEarned}</span>
              </div>
            </section>
          </section>
        </section>
      )}

      {tab === "directives" && (
        <section className="view directives">
          <section className="card objective-card">
            <span className="eyebrow">Mission Brief</span>
            <strong>Objective Focus</strong>
            <p>Attach an objective so the next directive lands as a concrete, useful action.</p>
            <textarea
              value={objectiveText}
              onChange={(event) => setObjectiveText(event.target.value)}
              placeholder="Example: Verify Fly memory posture, stabilize the mini app, and align ATLAS on the next deployment."
              rows={3}
            />
          </section>

          <section className="mission-grid">
            {missionCards.map((mission) => (
              <button key={mission.key} className={`directive-card ${mission.tone}`} onClick={mission.action}>
                <div className="directive-card-top">
                  <strong>{mission.title}</strong>
                  <span>{mission.reward}</span>
                </div>
                <p>{mission.summary}</p>
              </button>
            ))}
          </section>

          <section className="card action-runs-card">
            <div className="section-head">
              <div>
                <span className="eyebrow">Relay</span>
                <strong>Live Actions</strong>
              </div>
              <small>Command-backed</small>
            </div>
            {snapshot.recentDirectiveActions.length === 0 && <p className="action-empty">No action runs yet.</p>}
            {snapshot.recentDirectiveActions.slice(0, 6).map((run) => (
              <article key={run.id} className="action-item">
                <div className="action-item-head">
                  <strong>{directiveLabel(run.directive)}</strong>
                  <span className={`action-status ${run.status}`}>{actionStatusLabel(run.status)}</span>
                </div>
                <small>{new Date(run.createdAt).toLocaleString()}</small>
                {run.objective && <p>Objective: {run.objective}</p>}
                {run.responseText && <p>Result: {run.responseText}</p>}
                {run.error && <p>Error: {run.error}</p>}
              </article>
            ))}
          </section>

          <section className="card bindings-card">
            <div className="section-head">
              <div>
                <span className="eyebrow">Directive Intel</span>
                <strong>Bindings</strong>
              </div>
              <small>What each mission actually does</small>
            </div>
            <div className="binding-list">
              {snapshot.directiveBindings.map((binding) => (
                <article key={binding.directive} className="binding-item">
                  <h4>{binding.label}</h4>
                  <p>{binding.actionSummary}</p>
                  <small>{binding.objectiveHint}</small>
                </article>
              ))}
            </div>
          </section>
        </section>
      )}

      {tab === "log" && (
        <section className="view log-view">
          <EventTimeline
            events={snapshot.events}
            selectedId={selectedEvent?.id ?? null}
            onSelect={(event) => setSelectedEvent(event)}
          />
          {selectedEvent && (
            <article className="card event-detail">
              <span className="eyebrow">Log Detail</span>
              <h3>{selectedEvent.type.replaceAll("_", " ")}</h3>
              <small>{new Date(selectedEvent.createdAt).toLocaleString()}</small>
              <pre>{JSON.stringify(selectedEvent.payload, null, 2)}</pre>
            </article>
          )}
        </section>
      )}

      {panel === "inject" && (
        <section className="overlay" role="dialog" aria-modal="true">
          <article className="sheet">
            <span className="eyebrow">Mission Forge</span>
            <h3>Inject Task Packet</h3>
            <div className="options-grid">
              {taskPacketTypes.map((type) => (
                <button key={type} onClick={() => void runEvent("INJECT_TASK_PACKET", withObjective({ type }))}>
                  {type}
                </button>
              ))}
            </div>
            <button className="btn btn-secondary" onClick={() => setPanel("none")}>
              Close
            </button>
          </article>
        </section>
      )}

      {panel === "simulation" && (
        <section className="overlay" role="dialog" aria-modal="true">
          <article className="sheet">
            <span className="eyebrow">Drill Console</span>
            <h3>Simulation Run</h3>
            <div className="options-grid">
              {drillTypes.map((drillType) => (
                <div key={drillType} className="drill-row">
                  <strong>{drillType}</strong>
                  <div>
                    <button onClick={() => void runEvent("SIMULATION_RUN", { drillType, result: "pass" })}>Pass</button>
                    <button onClick={() => void runEvent("SIMULATION_RUN", { drillType, result: "fail" })}>Fail</button>
                  </div>
                </div>
              ))}
            </div>
            <button className="btn btn-secondary" onClick={() => setPanel("none")}>
              Close
            </button>
          </article>
        </section>
      )}

      {panel === "patches" && (
        <section className="overlay" role="dialog" aria-modal="true">
          <article className="sheet">
            <span className="eyebrow">Patch Bay</span>
            <h3>Orb upgrades</h3>
            <div className="patch-list">
              {snapshot.patches.map((patch) => (
                <div key={patch.id} className="patch-item">
                  <div>
                    <strong>{patch.name}</strong>
                    <p>{patch.description}</p>
                  </div>
                  <button disabled={patch.applied} onClick={() => void runPatch(patch.id)}>
                    {patch.applied ? "Applied" : "Apply"}
                  </button>
                </div>
              ))}
            </div>
            <h4>Install History</h4>
            <div className="history-list">
              {snapshot.events
                .filter((event) => event.type === "PATCH_APPLIED")
                .slice(0, 8)
                .map((event) => (
                  <p key={event.id}>{new Date(event.createdAt).toLocaleString()} · {(event.payload as { patchId: string }).patchId}</p>
                ))}
            </div>
            <button className="btn btn-secondary" onClick={() => setPanel("none")}>
              Close
            </button>
          </article>
        </section>
      )}

      {panel === "settings" && (
        <section className="overlay" role="dialog" aria-modal="true">
          <article className="sheet">
            <span className="eyebrow">Pilot Settings</span>
            <h3>Control deck</h3>
            <label>
              Notification Style
              <select
                value={state.settings.notificationStyle}
                onChange={(event) => void runEvent("SETTINGS_CHANGED", { key: "notificationStyle", value: event.target.value })}
              >
                <option value="standard">standard</option>
                <option value="minimal">minimal</option>
                <option value="verbose">verbose</option>
              </select>
            </label>
            <label>
              Risk Level
              <select
                value={state.settings.riskLevel}
                onChange={(event) => void runEvent("SETTINGS_CHANGED", { key: "riskLevel", value: event.target.value })}
              >
                <option value="low">low</option>
                <option value="balanced">balanced</option>
                <option value="high">high</option>
              </select>
            </label>
            <label className="toggle">
              <span>Pi Mode</span>
              <input
                type="checkbox"
                checked={state.settings.piMode}
                onChange={(event) => void runEvent("SETTINGS_CHANGED", { key: "piMode", value: event.target.checked })}
              />
            </label>
            <button className="btn btn-secondary" onClick={() => setPanel("none")}>
              Close
            </button>
          </article>
        </section>
      )}

      {error && <div className="error-banner">{error}</div>}

      <BottomNav active={tab} onChange={setTab} />
    </main>
  );
}
