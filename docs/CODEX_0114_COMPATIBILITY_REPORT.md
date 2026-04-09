# Codex 0.114.x Compatibility Report

Date: 2026-03-12
Target: Codex CLI `0.114.x` (verified at `0.114.0`)
Validated in repo: `/Users/corystoner/src/ORION` (Desktop symlink path also valid)

## Dependency Graph

- `T1` depends_on: `[]`
- `T2` depends_on: `[T1]`
- `T3` depends_on: `[T1]`
- `T4` depends_on: `[T1]`
- `T5` depends_on: `[T2, T3, T4]`
- `T6` depends_on: `[T5]`
- `T7` depends_on: `[T5]`
- `T8` depends_on: `[T6, T7]`

## Summary

Status: compatible with small hardening updates.

Validated areas:

- Handoff continuity: compatible after documenting transcript-aware delegation so ORION stops duplicating prior context.
- Permission flow: compatible at policy level; no Orion-side permission relaxation required, but approval persistence still needs one live interactive smoke test.
- Plugin workflow: compatible, but operator-facing docs now standardize on `@plugin`.
- App-server health: the repo previously lacked first-class `/readyz` and `/healthz` probe surfaces; that is now fixed.

## Evidence

Upstream Codex `0.114.0` signals:

- Realtime transcript handoff context, resumed-thread hardening, `request_permissions` persistence, reject-style config compatibility, legacy `workspace-write` compatibility, and websocket app-server `GET /readyz` plus `GET /healthz`: [openai/codex 0.114.0 release](https://github.com/openai/codex/releases/tag/rust-v0.114.0).

Local runtime checks:

- `codex --version` -> `codex-cli 0.114.0`
- `brew upgrade --cask codex` -> latest already installed (no newer stable release available)
- `brew info --cask codex` -> installed from Homebrew cask at `0.114.0`
- `codex --help` -> approval mode `on-request`, deprecated `on-failure`, sandbox mode `workspace-write`
- `codex app-server --help` -> app-server tooling is present in the local `0.114.0` install
- `openclaw --version` -> `OpenClaw 2026.3.8 (3caab92)`
- `openclaw config validate --json` -> valid runtime config
- `openclaw sessions cleanup --agent main --dry-run --fix-missing --json` -> cleanup path exists and reports stale session metadata without mutating state
- `bash scripts/stratus_healthcheck.sh --no-host` -> gateway health and service both `OK`
- `openclaw config get 'agents.list[0].subagents.allowAgents'` -> ORION delegation allowlist is present

## Change Matrix

| Area | Codex 0.114.x behavior | Orion before validation | Result |
| --- | --- | --- | --- |
| Handoffs | Realtime transcript context is passed across handoffs | Task Packet docs did not tell operators to avoid transcript restuffing | Updated docs/contracts |
| Resume | Reopened threads no longer stay stuck in-progress | Orion already required `queued` / `in progress` / `pending verification`, but lacked resume-specific guidance | Updated docs/contracts |
| Permissions | `request_permissions` persists across turns and supports reject-style configs; legacy `workspace-write` preserved | Orion policy docs were silent on runtime approval persistence | Updated docs/contracts |
| Plugin mentions | `$` picker clarifies Skills/Apps/Plugins and surfaces plugins first | Orion docs did not define one canonical operator-facing mention form | Standardized on `@plugin` in docs |
| App-server health | Websocket app-server exposes `/readyz` and `/healthz` | STRATUS only validated gateway health/status | Added routes, probe support, and config alignment |

## Files Updated

- `src/agents/ORION.md`
- `docs/TASK_PACKET.md`
- `docs/OPENCLAW_CONFIG_MIGRATION.md`
- `docs/CODEX_0114_COMPATIBILITY_REPORT.md`
- `scripts/stratus_healthcheck.sh`
- `tests/test_openclaw_workspace_contract.py`
- `tests/test_orion_instruction_contracts.py`
- `tests/test_stratus_healthcheck.py`

## Known-Safe Defaults

- Keep ORION security gates unchanged; persisted approvals are runtime plumbing, not broader authorization.
- Keep Task Packets concise on transcript-aware runtimes; pass deltas and artifact refs, not transcript dumps.
- Use `@plugin` in operator-facing prompts/docs.
- Prefer Codex approval mode `on-request` over deprecated `on-failure`.
- Keep `workspace-write` support only as a bounded sandbox mode, not as a trust signal.
- Probe liveness on `/healthz` and readiness on `/readyz`.
- Only enable optional STRATUS app-server checks when a Codex websocket app-server URL is explicitly configured.

## Remaining Validation Gaps

These still require one live operator smoke test outside this repo-only pass:

- real interactive approval persistence across turns/resume after a user approval
- live `@plugin` context attachment behavior in the Codex UI/runtime
- end-to-end interrupted-session resume using a real ORION -> specialist -> ORION chain

## Operator Checklist

1. Confirm local/runtime Codex is still on `0.114.x`: `codex --version`
2. Confirm readiness probe: `curl -fsS http://127.0.0.1:<port>/readyz`
3. Confirm liveness probe: `curl -fsS http://127.0.0.1:<port>/healthz`
4. Run one delegated ORION -> specialist -> ORION thread and confirm no duplicate announce output appears.
5. Run one permissioned task in `on-request` mode, approve it once, then resume the session and confirm no approval loop.
6. If using plugin references in operator prompts, use `@plugin` syntax.

## Rollback

- App-server probing is opt-in. Removing the `--app-server` flag or clearing `STRATUS_APP_SERVER_BASE_URL` / `CODEX_APP_SERVER_BASE_URL` restores previous STRATUS behavior.
