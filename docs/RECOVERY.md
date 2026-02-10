# ORION Recovery Runbook (Power Failure + Manual Restart)

This runbook covers what to do when ORION is offline, especially after a power failure, and what to check if AEGIS and/or launchd do not revive ORION automatically.

Related docs:
- AEGIS (remote sentinel): `docs/AEGIS_RUNBOOK.md`
- Incident log format: `INCIDENTS.md` + `tasks/INCIDENTS.md`
- One-command status snapshot (local + AEGIS): `./status.sh`

## Definitions

- **ORION host**: the Mac mini (launchd).
- **Gateway**: the local OpenClaw gateway service (`openclaw gateway ...`).
- **AEGIS**: the remote sentinel on Hetzner (systemd timers) that monitors ORION health and can run an allowlisted restart over restricted SSH.

## Quick Triage (Do This First)

1. Run the repo snapshot:
   - `./status.sh`
2. If ORION is unhealthy, get safe diagnostics (no secrets):
   - `scripts/stratus_healthcheck.sh`
   - `scripts/diagnose_gateway.sh`
3. If you take any recovery action (restart, repair, bypass), append an incident:
   - Prefer: `scripts/incident_append.sh ...`

## Power Failure (Cold Start) Checklist

1. Restore power and wait for the Mac mini to boot and join the network.
2. Confirm Tailscale is online on the Mac mini.
3. Check if the gateway auto-started:
   - `openclaw gateway status`
4. If not running:
   - `openclaw gateway start`
5. Confirm health:
   - `openclaw health`
6. If health still fails:
   - `openclaw doctor --repair`
   - `openclaw channels status --probe`
   - `openclaw logs --tail 200` (or re-run `scripts/diagnose_gateway.sh`)

Notes:
- If the Mac mini is up but no user session is logged in, launchd user agents may not run. In that case you may need to log in locally once, or intentionally migrate the gateway to a boot-level service (explicit decision; see `SECURITY.md`).

## If AEGIS Did Not Revive ORION

AEGIS can only revive ORION once the Mac mini is reachable over Tailscale SSH and the restricted forced-command allowlist is still valid.

1. Check AEGIS status from the Mac mini repo:
   - `./status.sh` (see the “AEGIS (Remote) last_ok + logs” section)
2. Common blockers:
   - ORION host is actually down (power/network).
   - Tailscale is down on either host.
   - SSH key or the Mac mini forced-command allowlist changed (AEGIS can connect but commands are rejected).
   - Restart guard is active (AEGIS intentionally paused restarts to prevent flapping).
3. If restart guard is active:
   - Expect AEGIS to resume automatically after the rolling window cools down.
   - Optional manual clear is documented in `docs/AEGIS_RUNBOOK.md`.
4. If ORION is up but gateway is not:
   - Run locally: `scripts/resurrect_orion_mac.sh`

## Manual Recovery (Local-First)

When ORION is down and you have local access to the Mac mini:

1. Soft restart:
   - `openclaw gateway restart`
2. If restart fails (service missing or broken):
   - `openclaw gateway install`
   - `openclaw gateway start`
3. Repair + probe:
   - `openclaw doctor --repair`
   - `openclaw security audit --deep`
   - `openclaw channels status --probe`
4. Validate bindings and model routing:
   - `openclaw agents list --bindings`
   - `openclaw models status`

Shortcut:
- `scripts/resurrect_orion_mac.sh` runs the above sequence as a single script.

## Optional: Auto-Resurrection At Login (macOS)

If you want the Mac mini to run a best-effort “resurrection” once on login after reboot:

- Install the LaunchAgent:
  - `scripts/install_orion_resurrector_launchagent.sh /Users/corystoner/Desktop/ORION`
- Logs:
  - `~/Library/Logs/orion_resurrector.log`

This is intentionally login-scoped (LaunchAgent). It is not a boot-level daemon.

## After Recovery (Hard Requirement)

1. Append an `INCIDENT v1` entry to `tasks/INCIDENTS.md` if you restarted anything or hit a safety bypass.
2. Create a follow-up Task Packet for prevention if the issue can repeat (bad config, provider outage, auth drift, disk pressure).
