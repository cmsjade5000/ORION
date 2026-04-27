# T5 Upgrade/Tool Utilization Matrix

## Scope
- Local surface: `/Users/corystoner/src/ORION`
- OpenClaw notes checked: `v2026.4.20`, `v2026.4.21`, `v2026.4.25` (GitHub releases API)
- Date: `2026-04-27`

| Item | Upstream note | Local evidence | Status | Owner | Action |
| --- | --- | --- | --- | --- | --- |
| Cron state split between `jobs.json` and `jobs-state.json` | `2026.4.20` says split runtime execution state into `jobs-state.json` so definitions stay stable | `~/.openclaw/cron/jobs.json` and `~/.openclaw/cron/jobs-state.json` both present and parsed in T1/T6 evidence | pass | ORION | Keep both files in canonical read path; continue explicit queue validation |
| Owner command auth hardening (`owner identity` / `owner-candidate` validation) | `2026.4.21` enforces owner identity for owner commands | OpenClaw CLI canary confirms `commands.ownerAllowFrom` is writable (`openclaw config set ... --dry-run` and live write, then returned in `openclaw config get commands`); baseline still has no active allowlist keys and `openclaw security audit --json` shows no owner-specific checks surfaced in this snapshot | warn | ORION | Keep one operational owner-auth sanity packet in the next T5 pass (explicit non-owner command attempt) to convert from canary path to hard allow/deny evidence |
| Cron overlap guard + deprecated wrapper removal | Upstream duplicate/maintenance scheduler fixes in `v2026.4.20+` and subsequent scheduler hardening | Installer cleanup and runtime evidence show `ai.orion.inbox_packet_runner` + `com.openclaw.orion.assistant_task_loop` removed, `assistant-task-loop` absent from `~/.openclaw/cron/jobs.json`, and overlap guard returns no overlaps | pass | ORION | Retain one-pass cleanup script rule and weekly overlap check |
| Task delivery outcome contract and dead-lettering | No exact 1:1 note in pulled body; aligns with hardened outbound diagnostics in `2026.4.25` | `scripts/notify_inbox_results.py` writes `delivered`/`suppressed`/`failed-to-deliver`, state in `tmp/inbox_notify_state.json`, dead letters in `tmp/inbox_notify_dead_letters.jsonl` | pass | ORION | Keep as canonical notification contract |
| Plugin/runtime registry migration to persisted registry | `2026.4.25` and plugin notes mention moved persisted registry surfaces | `T1_toolset_audit.json` shows `runtime.plugins_inventory.registry.source: persisted`; persisted registry loaded and audits include enabled plugins | pass | ORION | Keep plugin registry health check in T5 matrix |
| OpenAI Codex routing and transport normalization | `2026.4.20-4.21` include Codex transport/auth fixes and fallback behavior | `T1_toolset_audit.json` reports `codex_version: 0.125.0` and auth-valid config; no regressions observed during sweep | pass | ATLAS | Track Codex-specific path changes in future run notes |
| Session pruning/OOM prevention updates | `2026.4.20` notes prune built-in entry caps and load-time session cleanup | Sweep is currently queue-focused; no explicit session-store stress test run in this pass | warn | ORION | Add dedicated session-maintenance stress check in next operator pass |
| Queue lifecycle hardening for `pending_verification`/`queued` invariants | Upstream scheduler/queue consistency work in modern releases | `scripts/collect_reliability_snapshot.py` now emits `queued` and `pending_verification` health, stale buckets, and SLO thresholds | pass | ORION | Enforce hard stop gates before next workflow batch |

## No-Drift Notes
- Telegram-only enforcement is consistent with ORION sweep scope; Discord path remains compatibility-only and not part of default cron schedule.
- No upstream tags in scope introduced direct dependency requiring immediate queue-schema migration beyond existing durability contract.
