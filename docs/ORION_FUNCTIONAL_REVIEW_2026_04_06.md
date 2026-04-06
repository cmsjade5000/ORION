# ORION Functional Review 2026-04-06

Status: implemented review artifact

This review follows the stabilization tranche and focuses on user-visible behavior,
operator workflow, and the gap between intended orchestration and the mechanisms
the repo actually relies on today.

## Dependency Graph

- `T1` depends_on: `[]`
- `T2` depends_on: `[T1]`
- `T3` depends_on: `[T1]`
- `T4` depends_on: `[T2, T3]`
- `T5` depends_on: `[T4]`

## T1. Re-Baseline

Current baseline on 2026-04-06:

- `openclaw status --all` reports OpenClaw `2026.4.5`, gateway reachable, Telegram `OK`, Discord `OK`.
- `python3 scripts/task_execution_loop.py --repo-root . --apply --stale-hours 24` refreshed:
  - [status.md](/Users/corystoner/Desktop/ORION/tasks/NOTES/status.md)
  - [plan.md](/Users/corystoner/Desktop/ORION/tasks/NOTES/plan.md)
- `python3 scripts/orion_error_db.py review --window-hours 24 --json` still produces:
  - [error-review.md](/Users/corystoner/Desktop/ORION/tasks/NOTES/error-review.md)

Current live workflow shape:

- Telegram request handling is a thin command adapter around local scripts, not a free-form conversational runtime.
- Durable delegation is inbox-backed through Task Packets and scheduled loops, not session-backed.
- POLARIS is still the intended admin orchestrator and ATLAS is still the intended ops director.

## T2. Workflow Review

### Request Intake And Routing

- `/today`, `/capture`, `/followups`, and `/review` are deterministic wrappers over local scripts and packet append behavior.
- `/capture` is the cleanest functional seam: it turns Telegram input into intake state plus a POLARIS Task Packet.
- The intended session-native delegation path (`sessions_spawn`, later `sessions_yield`) is documented, but the reliable async path is really packet + cron/LaunchAgent reconciliation.

### Long-Running Work And Follow-Through

- Follow-through is durable only after work is converted into inbox packets plus scheduled loop handling.
- `sessions_yield` is policy/documentation only today; there is no repo implementation using it.
- Stale packets remain the clearest user-facing symptom of incomplete follow-through:
  - long-open SCRIBE packet
  - long-open AEGIS plan watch packet
  - long-open ATLAS AEGIS deploy packet

### Outbound Reporting And Milestones

- Outbound reporting is split across multiple paths:
  - direct Telegram/API sends
  - `openclaw message send`
- This creates duplicate formatting logic and increases drift risk between Telegram and Discord updates.
- Milestone update policy exists, but execution is spread across notifier scripts and packet conventions rather than one normalized status object.

### Review And Maintenance Loops

- `task_execution_loop.py` is a repo reconciliation engine with runtime probes attached.
- `notify_inbox_results.py`, `task_execution_loop.py`, `session_maintenance.py`, and `orion_error_db.py` each maintain part of the async lifecycle.
- The result is functional coverage, but not one coherent delegated-job model.

## T3. High-Value Functional Replacements

### Replace Documented `sessions_yield` Preference With The Actual Async Primitive

Preferred functional model:

- create Task Packet
- record queue state
- notify once on queue
- reconcile periodically
- emit one normalized final result

This matches the proven repo mechanism better than pretending session-native yield is already the durable path.

### Replace Per-Surface Outbound Logic With One Delivery Adapter

Preferred functional model:

- one sanitized result object
- one canonical formatter
- one delivery adapter per channel

Telegram and Discord should consume the same result payload rather than each path formatting the same work independently.

### Replace Inferred Handoff State With A Durable Delegated Job Record

Current state is inferred from:

- inbox markdown
- notifier state hashes
- ticket lanes
- runtime task audit

Preferred functional model:

- one durable per-job artifact with queue, in-progress, checkpoint, blocked, and complete state
- packet and notification systems read from that artifact instead of inferring state ad hoc

### Replace Duplicate Maintenance Schedulers With One Canonical Runner

`local_job_runner.py` and `orion_local_maintenance_runner.sh` overlap on assistant task-loop scheduling.

Preferred functional model:

- one canonical scheduler/runner definition
- thin wrappers only when platform-specific launch plumbing is needed

## T4. Prioritized Functional Improvement Shortlist

### Ready Next

1. Unify outbound result delivery around one normalized result object and one Telegram-first adapter.
2. Introduce a durable delegated-job status artifact for Task Packet work.
3. Make stale packet escalation user-visible and operator-actionable before work ages into silent backlog.
4. Collapse duplicate maintenance scheduling into one canonical job runner.

### Needs Evidence

1. Use PULSE as the owner of durable async workflow state rather than leaving it spread across notifier and reconcile loops.
2. Replace more Telegram command wrappers with a shared typed command/result layer.

### Remove Or De-Emphasize

1. Treat `sessions_yield` as implemented functionality in docs.
2. Keep separate result fan-out logic per channel.

## T5. Next Implementation Tranche

Title: Delegated Job Model And Unified Delivery

### Summary

Build one functional layer for delegated work that sits between Task Packets and user-facing updates.

### Changes

- Add a durable delegated-job record for packet-backed workflows.
- Teach queue/reconcile/notifier flows to read and update that record instead of inferring all state from inbox markdown and task audits.
- Unify Telegram and Discord updates around one normalized result structure.
- Keep Telegram as the primary user-facing surface.

### What To Avoid

- Do not add new integrations before the delegated-job model exists.
- Do not broaden session-native orchestration until the packet-backed async model is first-class.
- Do not preserve multiple outbound formatting stacks once one canonical adapter is in place.

### Acceptance Criteria

- A delegated packet has one durable state source from queued to complete.
- ORION follow-through no longer depends on reading several independent state stores to know what happened.
- Telegram and Discord can show the same result without duplicate business logic.
- Stale delegated work is surfaced as a first-class functional issue, not only a maintenance note.
