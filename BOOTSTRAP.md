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
3. Validate the active runtime config before starting the gateway:
   ```bash
   openclaw config validate --json
   ```
   - As of OpenClaw `2026.3.x`, new local installs default to `tools.profile=messaging` when unset.
   - ORION expects `tools.profile` pinned to `coding` in local installs.
4. Verify model routing (Gemini primary):
   ```bash
   openclaw models status
   ```
   - If you still need provider keys:
     - Gemini key (needed for chat + image generation): see `docs/LLM_ACCESS.md`
     - Optional: NVIDIA Build key (only if you enable Kimi 2.5 fallback): see `docs/NVIDIA_BUILD_KIMI.md`
   - Recommended auth setup (best for LaunchAgent reliability):
     ```bash
     openclaw models auth paste-token --provider google
     openclaw models status --probe
     ```
5. Verify Telegram token file exists and is locked down (`600`):
   - Config uses `channels.telegram.tokenFile`
   - Token file should contain only the raw token + newline
6. Install and start the gateway service (required for cron reliability):
   ```bash
   openclaw gateway install
   openclaw gateway start
   ```
7. Repair and harden:
   ```bash
   openclaw doctor --repair
   openclaw security audit --deep
   ```
8. Verify channel health:
   ```bash
   openclaw channels status --probe
   ```
   - Fast triage summary (local + AEGIS remote):
     ```bash
     ./status.sh
     ```
9. Verify delegation (ORION -> ATLAS via `sessions_spawn` + Task Packet):
   - Use `docs/TASK_PACKET.md`
   - Specialists never message Telegram directly
10. Add minimal cron jobs (optional; keep delivery off unless explicitly wanted):
   - Use `skills/cron-manager`
11. (Optional) Email toolchain (ORION-only):
   - Store AgentMail key at `~/.openclaw/secrets/agentmail.api_key` (chmod `600`)
   - Smoke test:
     ```bash
     node -e "require('./skills/agentmail/manifest').listInboxes().then(console.log)"
     ```

## Post-Bootstrap

- Delete this file (`BOOTSTRAP.md`) after go-live so it stops being injected.
- Keep ongoing state in `memory/WORKING.md` and `tasks/`.
