# BOOTSTRAP.md (One-Time)

OpenClaw injects `BOOTSTRAP.md` on the first turn of a new session. This file is intended to be temporary.

When this checklist is complete and the gateway is stable, delete `BOOTSTRAP.md` to keep prompts lean.

## Go-Live Checklist (Mac mini, local-first)

1. Regenerate SOULs (source-of-truth lives in `src/core/shared/` and `src/agents/`):
   ```bash
   make soul
   ```
2. Verify OpenClaw sees all isolated agents (ORION + specialists):
   ```bash
   openclaw agents list
   ```
3. Verify model routing (OpenRouter primary, Gemini fallback):
   ```bash
   openclaw models status
   ```
4. Verify Telegram token file exists and is locked down (`600`):
   - Config uses `channels.telegram.tokenFile`
   - Token file should contain only the raw token + newline
5. Install and start the gateway service (required for cron reliability):
   ```bash
   openclaw gateway install
   openclaw gateway start
   ```
6. Repair and harden:
   ```bash
   openclaw doctor --repair
   openclaw security audit --deep
   ```
7. Verify channel health:
   ```bash
   openclaw channels status --probe
   ```
8. Verify delegation (ORION -> ATLAS via `sessions_spawn` + Task Packet):
   - Use `docs/TASK_PACKET.md`
   - Specialists never message Telegram directly
9. Add minimal cron jobs (optional; keep delivery off unless explicitly wanted):
   - Use `skills/cron-manager`

## Post-Bootstrap

- Delete this file (`BOOTSTRAP.md`) after go-live so it stops being injected.
- Keep ongoing state in `memory/WORKING.md` and `tasks/`.
