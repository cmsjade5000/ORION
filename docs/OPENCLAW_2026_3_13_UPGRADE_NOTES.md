# OpenClaw 2026.3.13 Upgrade Notes

Local runtime was upgraded on 2026-03-15 from `2026.3.11` to `2026.3.13`.

Verification:

```bash
openclaw --version
openclaw gateway status
openclaw config validate --json
```

Observed result after upgrade:
- CLI version: `OpenClaw 2026.3.13`
- Gateway runtime: healthy RPC probe on the local LaunchAgent
- Runtime config: valid

Official upstream sources:
- `v2026.3.12`: <https://github.com/openclaw/openclaw/releases/tag/v2026.3.12>
- `v2026.3.13-1`: <https://github.com/openclaw/openclaw/releases/tag/v2026.3.13-1>

## What Changed That Matters To ORION

Most upstream changes in this window are UI, onboarding, or broad security work. The items that materially affect ORION are:

- `fix(cron): prevent isolated cron nested lane deadlocks`
  - This directly helps ORION's assistant crons, inbox notifier, follow-through loops, and other isolated automation lanes.
- `fix: resolve target agent workspace for cross-agent subagent spawns`
  - This matters for ORION -> ATLAS/POLARIS/... delegation because the runtime now resolves the target agent workspace more reliably.
- `fix(agents): avoid injecting memory file twice on case-insensitive mounts`
  - This is relevant on macOS and reduces prompt bloat/noise for ORION's memory-backed sessions.
- `fix(gateway): bound unanswered client requests`
  - This should reduce stuck client/gateway interactions and improve recovery under degraded conditions.
- `Gateway: treat scope-limited probe RPC as degraded reachability`
  - This improves health semantics for gateway checks instead of reporting misleading fully-healthy status.
- `perf(build): deduplicate plugin-sdk chunks to fix ~2x memory regression`
  - This reduces memory pressure in OpenClaw UI/build paths.
- `Plugins: fail fast on channel and binding collisions`
  - This makes routing/config mistakes surface earlier, which is useful in a multi-agent ORION workspace.
- `Agents/subagents: add sessions_yield`
  - This is the main new orchestration primitive worth adopting later for long-running ORION specialist workflows.

## ORION Impact

Immediate runtime gains after the upgrade:

- More reliable isolated cron execution for assistant automation.
- Safer cross-agent workspace handling, which aligns with ORION's normalized `/Users/corystoner/src/ORION` workspace path.
- Less prompt duplication risk from memory injection on macOS.
- Better gateway resilience and more accurate degraded-health reporting.

These benefits are primarily runtime-level. ORION gets them once the gateway is updated and restarted; most do not require repo code changes.

## What We Implemented In This Repo

To align ORION with the newer runtime:

- Normalized the canonical workspace path to `/Users/corystoner/src/ORION` in live templates/docs.
- Kept assistant automation centered on isolated, repo-backed flows:
  - `/today`
  - `/capture`
  - `/followups`
  - `/review`
- Promoted `POLARIS` as the default admin-workflow orchestrator.
- Pinned memory-hook and plugin expectations in the OpenClaw templates:
  - `session-memory`
  - `command-logger`
  - `memory-lancedb`
  - `open-prose`
- Added regression coverage so these assumptions do not drift silently.

## Recommended Next Performance Steps

1. Keep using isolated cron lanes for assistant automation now that the upstream deadlock fix is in place.
2. Add `openclaw agents bindings --json` and `openclaw plugins list --json` to post-change verification whenever routing or channel config changes.
3. Evaluate `sessions_yield` for long-running ATLAS/POLARIS workflows where ORION should end the current turn quickly and let work continue in the next turn.
   - Good candidates: overnight review, long director-style ATLAS execution, and bounded admin follow-through that already has a user-facing acknowledgement.
4. Keep workspace-path normalization strict. The upstream cross-agent workspace fix is most useful when ORION's workspace path is unambiguous.
5. Treat gateway health as `healthy` vs `degraded`, not just `up` vs `down`, when wiring future watchdogs or recovery scripts.

## Notes

- The updater touched `~/.openclaw/openclaw.json` metadata during the upgrade and created `~/.openclaw/openclaw.json.bak`.
- In this run, the config diff was metadata/plugin-install timestamp churn rather than a breaking schema rewrite.
