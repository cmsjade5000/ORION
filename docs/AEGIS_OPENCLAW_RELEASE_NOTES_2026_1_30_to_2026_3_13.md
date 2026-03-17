# AEGIS OpenClaw Release Notes (`2026.1.30` -> `2026.3.13`)

This note tracks the upstream OpenClaw changes that mattered during the AEGIS
upgrade from `2026.1.30` to `2026.3.13` on March 16, 2026.

## Versions Reviewed

- `2026.2.6`
- `2026.2.19`
- `2026.2.23`
- `2026.2.24`
- `2026.2.25`
- `2026.2.26`
- `2026.3.1`
- `2026.3.2`
- `2026.3.7`
- `2026.3.8`
- `2026.3.11`
- `2026.3.12`
- `2026.3.13`
- Upstream follow-on tag observed during review: `2026.3.13-1`

## AEGIS-Relevant Changes

- `2026.2.6`: stronger redaction/scanners and cron hardening.
- `2026.2.19`: `openclaw security audit --deep` added materially useful
  gateway auth coverage.
- `2026.2.23` and `2026.3.2`: additional config and secret redaction hygiene.
- `2026.2.24`: broader trust-model audit heuristics.
- `2026.2.25`: heartbeat/default-delivery behavior changed; AEGIS must recheck
  single-bot posture after upgrades instead of trusting old assumptions.
- `2026.2.26`: `openclaw secrets` and `openclaw sessions cleanup` became
  first-class operational tools.
- `2026.3.1`: built-in `/health`, `/healthz`, `/ready`, and `/readyz`.
- `2026.3.7`: explicit gateway auth-mode handling became more important when
  multiple auth surfaces exist.
- `2026.3.8`: restart/catch-up reliability improved.
- `2026.3.11`: stricter websocket and browser-origin validation.
- `2026.3.12`: pairing/bootstrap-token and plugin auto-load hardening.
- `2026.3.13`: cron deadlock fixes, degraded-health tightening, bounded gateway
  request handling, and more collision checks.

## Applied On AEGIS

- Upgraded host runtime to `2026.3.13`.
- Added release-aware checks to the maintenance/runbook docs:
  - secrets audit
  - sessions cleanup dry run
  - heartbeat/default-delivery review
  - health endpoint verification
- Kept `gateway.auth.mode=token` explicit.
- Kept the rejected legacy keys out of runtime config:
  - `agents.defaults.heartbeat.directPolicy`
  - `commands.ownerDisplay`

## Deferred / Residual

- A plaintext-token cleanup experiment moved the gateway token into a service
  env file successfully, but the fully env-only config shape caused unstable
  local loopback probe behavior on the live host. Do not treat that migration as
  complete yet.
- After the `2026.3.13` upgrade, the local loopback probe path on the AEGIS
  host showed inconsistent behavior across:
  - `openclaw health`
  - `openclaw status --all`
  - `openclaw security audit --deep`
  - direct `/readyz` / `/healthz` checks
- Treat any future `missing scope: ...`, `device signature invalid`, or
  loopback probe regressions as upgrade follow-up signals, not normal noise.
