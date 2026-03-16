# Scripts

This directory contains maintenance, build, and automation scripts for the Gateway system.

Scripts here are intended to be:
- explicit
- repeatable
- safe to run locally
- version-controlled

Nothing in this directory should modify secrets directly.

---

## sessions_hygiene.sh

### Purpose
Run OpenClaw session-store hygiene for one agent with a safe default dry-run preview and optional apply mode.

### Usage

Dry-run preview (safe default):

```bash
./scripts/sessions_hygiene.sh --agent main --fix-missing
```

Apply cleanup (requires explicit gate):

```bash
AUTO_OK=1 ./scripts/sessions_hygiene.sh --agent main --fix-missing --doctor --apply
```

---

## telegram_topic_bindings_bootstrap.sh

### Purpose
Bootstrap Telegram forum topic routing to specialist agents by writing per-topic `agentId` config and ensuring topic-scoped route bindings.

### Usage

Dry-run:

```bash
./scripts/telegram_topic_bindings_bootstrap.sh \
  --group-id -1001234567890 \
  --topic 1:main \
  --topic 7:atlas \
  --topic 9:ledger
```

Apply:

```bash
./scripts/telegram_topic_bindings_bootstrap.sh \
  --group-id -1001234567890 \
  --topic 1:main \
  --topic 7:atlas \
  --topic 9:ledger \
  --apply
```

---

## discord_selfcheck.sh

### Purpose
Verifies that OpenClaw's Discord plugin is enabled and `channels.discord` is configured safely (best-effort probe; does not print tokens).

### Usage

```bash
./scripts/discord_selfcheck.sh
```

---

## discord_send_message.sh

### Purpose
Send a Discord message via OpenClaw's Discord channel plugin.

### Usage

```bash
./scripts/discord_send_message.sh user:<DISCORD_USER_ID> "hi"
./scripts/discord_send_message.sh channel:<DISCORD_CHANNEL_ID> "update"
```

Read message from stdin:

```bash
printf '%s\n' "multi-line\nmessage" | ./scripts/discord_send_message.sh channel:<DISCORD_CHANNEL_ID> -
```

---

## discord_thread_create.sh

### Purpose
Create a task thread in a Discord channel via OpenClaw.

### Usage

```bash
./scripts/discord_thread_create.sh channel:<DISCORD_CHANNEL_ID> "task: triage" "starting thread"
```

---

## discord_thread_reply.sh

### Purpose
Reply in an existing Discord thread via OpenClaw.

### Usage

```bash
./scripts/discord_thread_reply.sh channel:<DISCORD_THREAD_ID> "progress update"
```

---

## discord_autonomy_bootstrap.sh

### Purpose
Apply a high-autonomy Discord configuration for ORION in a specific guild and print a broad non-admin bot invite URL.

### Usage

```bash
./scripts/discord_autonomy_bootstrap.sh <DISCORD_APP_ID> <DISCORD_GUILD_ID> <DISCORD_PRIMARY_CHANNEL_ID> [DISCORD_UPDATES_CHANNEL_ID]
```

---

## miniapp_upload_artifact.sh

### Purpose
Uploads a file (PDF/export/etc.) to the Telegram Mini App dashboard API so it appears as a floating artifact bubble that the user can tap to download.

### Usage

```bash
INGEST_TOKEN=... ./scripts/miniapp_upload_artifact.sh https://<miniapp-host> ./out/xyz.pdf xyz.pdf application/pdf LEDGER
```

---

## miniapp_command_relay.py

### Purpose
Claims queued Mini App commands from `/api/relay/claim`, executes them with local `openclaw`, and reports completion back to `/api/relay/:id/result`.

Use this when the Mini App server is deployed remotely (for example Fly) and cannot run `openclaw` itself.

### Usage

```bash
MINIAPP_COMMAND_RELAY_URL=https://<miniapp-host> \
MINIAPP_COMMAND_RELAY_TOKEN=... \
python3 scripts/miniapp_command_relay.py
```

One-shot mode:

```bash
MINIAPP_COMMAND_RELAY_URL=https://<miniapp-host> \
MINIAPP_COMMAND_RELAY_TOKEN=... \
python3 scripts/miniapp_command_relay.py --once
```

Persistent macOS service (LaunchAgent):

```bash
./scripts/install_orion_miniapp_command_relay_launchagent.sh /Users/corystoner/src/ORION
```

---

## telegram_open_miniapp.sh

### Purpose
Sends an inline `web_app` button to the allowlisted Telegram user so you can open the Mini App without hunting for the URL.

### Usage

```bash
./scripts/telegram_open_miniapp.sh
```

Optional URL override:

```bash
./scripts/telegram_open_miniapp.sh https://<miniapp-host>
```

---

## assistant_status.py

### Purpose
Build the generated assistant agenda/status views used by `/today`, `/followups`, and `/review`.

### Usage

```bash
python3 scripts/assistant_status.py --cmd today --json
python3 scripts/assistant_status.py --cmd refresh --json
```

---

## assistant_capture.py

### Purpose
Create a quick intake item and queue a POLARIS packet for bounded admin follow-through.

### Usage

```bash
python3 scripts/assistant_capture.py --text "Follow up with the contractor next Tuesday." --json
```

---

## assistant_memory.py

### Purpose
Persist and recall small local assistant-memory items. This complements OpenClaw memory hooks; it does not replace them.

### Usage

```bash
python3 scripts/assistant_memory.py remember --text "Cory prefers bounded proactive follow-through."
python3 scripts/assistant_memory.py recall --query "bounded proactive" --json
```

---

## orion_error_db.py

### Purpose
Track recurring ORION operational errors in a repo-local sqlite DB and run a nightly review that can apply a small allowlist of safe remediations.

### Usage

```bash
python3 scripts/orion_error_db.py stats --json
python3 scripts/orion_error_db.py review --window-hours 24 --json
python3 scripts/orion_error_db.py review --window-hours 24 --apply-safe-fixes --escalate-incidents --json
```

---

## install_orion_assistant_crons.sh

### Purpose
Print or install the lightweight assistant crons for agenda refresh, inbox notifications, and stale-work reconciliation.
It also installs the nightly ORION error-review cron.

### Usage

```bash
./scripts/install_orion_assistant_crons.sh
./scripts/install_orion_assistant_crons.sh --apply
```

---

## assistant_skill_refresh.sh

### Purpose
Print or run the monthly assistant skill-refresh commands (ClawHub plus local discovery scan).

### Usage

```bash
./scripts/assistant_skill_refresh.sh
./scripts/assistant_skill_refresh.sh --apply
```

---

## telegram_send_message.sh

### Purpose
Send a Telegram message with optional real-time draft streaming (`sendMessageDraft`) before the final `sendMessage`.
Supports safe defaults for preview suppression, optional parse mode, reply-to, and long-message chunking.

### Usage

```bash
./scripts/telegram_send_message.sh <chat_id> "message text"
```

Enable draft streaming:

```bash
TELEGRAM_STREAM_DRAFT=1 ./scripts/telegram_send_message.sh <chat_id> "longer message..."
```

Tune stream pacing:

```bash
TELEGRAM_STREAM_DRAFT=1 TELEGRAM_STREAM_CHUNK_CHARS=320 TELEGRAM_STREAM_STEP_MS=180 \
  ./scripts/telegram_send_message.sh <chat_id> "longer message..."
```

Enable HTML parse mode:

```bash
TELEGRAM_PARSE_MODE=HTML ./scripts/telegram_send_message.sh <chat_id> "<b>bold</b>"
```

Enable web previews:

```bash
TELEGRAM_DISABLE_WEB_PREVIEW=0 ./scripts/telegram_send_message.sh <chat_id> "https://example.com"
```

Reply to a specific message id:

```bash
TELEGRAM_REPLY_TO_MESSAGE_ID=1234 ./scripts/telegram_send_message.sh <chat_id> "Acknowledged."
```

Force chunking for long messages:

```bash
TELEGRAM_MAX_CHARS=1200 ./scripts/telegram_send_message.sh <chat_id> "$(cat long_message.txt)"
```

Notes:
- If Telegram draft APIs are unavailable for the chat/bot, the script falls back to normal `sendMessage`.
- Final `sendMessage` is sent once even when draft streaming fails.
- `ORION_SUPPRESS_TELEGRAM=1` still suppresses send operations (dry-run safety).
- Optional override: `TELEGRAM_STREAM_DRAFT_ID=<positive-int>` to force a deterministic draft animation id.

---

## install_orion_personal_ops_crons.sh

### Purpose
Upsert two lightweight weekday personal-ops cron jobs for ORION:
- morning brief
- evening reset

Defaults to dry-run; pass `--apply` to persist changes.

### Usage

Dry-run:

```bash
./scripts/install_orion_personal_ops_crons.sh
```

Apply:

```bash
./scripts/install_orion_personal_ops_crons.sh --apply
```

Customize schedule/timezone:

```bash
./scripts/install_orion_personal_ops_crons.sh \
  --apply \
  --morning-cron "15 7 * * 1-5" \
  --evening-cron "30 20 * * 1-5" \
  --tz "America/New_York"
```

---

## pogo_extract.mjs

### Purpose
Parse official Pokemon GO `news` and `events` pages into structured JSON for automation-safe brief generation.

### Usage

```bash
node scripts/pogo_extract.mjs \
  --news-html /tmp/news.html \
  --events-html /tmp/events.html \
  --tz America/New_York
```

---

## pogo_brief_inputs.sh

### Purpose
Build the Pokemon GO morning-brief input payload:
- official event/news cards + freshness/confidence
- shiny-signal extraction
- calendar-aware `R096` work-shift + commute checks
- urgency tier + weekly story arc line

### Usage

```bash
./scripts/pogo_brief_inputs.sh
```

---

## pogo_morning_voice_send.sh

### Purpose
Send a 60-second shiny-first Pokemon GO voice brief to Telegram via ElevenLabs TTS, with optional follow-up links.

### Usage

Dry-run:

```bash
./scripts/pogo_morning_voice_send.sh
```

Send now:

```bash
./scripts/pogo_morning_voice_send.sh --send
```

Prompt-only ask (voice or text):

```bash
./scripts/pogo_morning_voice_send.sh --send --prompt-only
```

Text-only fallback:

```bash
./scripts/pogo_morning_voice_send.sh --send --text-only
```

---

## pogo_brief_commands.py

### Purpose
Deterministic text command responses for Telegram slash-like prompts:
- `help`
- `today`
- `status`

### Usage

```bash
python3 scripts/pogo_brief_commands.py --cmd help
python3 scripts/pogo_brief_commands.py --cmd voice
python3 scripts/pogo_brief_commands.py --cmd text
python3 scripts/pogo_brief_commands.py --cmd today
python3 scripts/pogo_brief_commands.py --cmd status
```

---

## soul_factory.sh

### Purpose
`soul_factory.sh` generates per-agent `SOUL.md` files from modular source-of-truth identity components.

It combines:
- shared constitutional rules
- shared foundational identity
- shared routing logic
- a single agent role definition

into a final, agent-specific `SOUL.md`.

---

### Source of Truth

Inputs:
- `src/core/shared/`
- `src/agents/`

Output:
- `agents/<AGENT>/SOUL.md`

Generated files should never be edited by hand.

---

### Usage

Generate SOULs for all agents:
```bash
./scripts/soul_factory.sh --all
```

---

## arb_bot.py / arb_scan.sh

### Purpose
Read-only Polymarket arb scanner (detects simple within-market YES/NO buy-both arbs from order books).

### Usage

```bash
python3 scripts/arb_bot.py scan --max-markets 10 --min-edge-bps 20
```

Wrapper:

```bash
./scripts/arb_scan.sh --max-markets 10 --min-edge-bps 20
```

Notes:
- This is intentionally read-only; it does not place orders.
- See `docs/ARB_BOT.md`.

---

## kalshi_ref_arb.py

### Purpose
Kalshi crypto reference arb bot (scan Kalshi markets; optionally trade with explicit `--allow-write` and local credentials).

### Usage

Scan:

```bash
python3 scripts/kalshi_ref_arb.py scan --series KXBTC --limit 10
```

Trade (dry-run unless `--allow-write`):

```bash
python3 scripts/kalshi_ref_arb.py trade --series KXBTC --limit 10
```

Docs:
- `docs/KALSHI_REF_ARB.md`

---

## kalshi_autotrade_cycle.py

### Purpose
Deterministic Kalshi autotrade cycle runner intended for OpenClaw cron (no manual operation):
- runs `kalshi_ref_arb.py balance`
- runs `kalshi_ref_arb.py trade --allow-write` with conservative caps and a $50 lifetime budget
- writes artifacts under `tmp/kalshi_ref_arb/runs/`
- sends Telegram notifications only on live orders or errors (rate-limited)

### Grouped-Round Gate Tuning (paper mode)
`kalshi_autotune.py` now supports grouped round-by-round gate adaptation from sweep stats:
- evaluate the latest `round_cycles * groups_lookback` cycles
- score multiple gate-change options from blocker mix
- apply bounded changes at most once per completed round
- continue nudging until opportunity flow is in-range

Key env knobs:
- `KALSHI_ARB_TUNE_SWEEP_ROUND_CYCLES` (default `12`)
- `KALSHI_ARB_TUNE_SWEEP_GROUPS_LOOKBACK` (default `3`)
- `KALSHI_ARB_TUNE_SWEEP_MIN_ROUNDS` (default `2`)
- `KALSHI_ARB_TUNE_SWEEP_MAX_CHANGES_PER_ROUND` (default `2`)
- `KALSHI_ARB_TUNE_SWEEP_TARGET_MIN_RECOMMENDED` (default `1`)
- `KALSHI_ARB_TUNE_SWEEP_TARGET_MAX_RECOMMENDED` (default `8`)
- `KALSHI_ARB_TUNE_SWEEP_TARGET_MIN_PLACED` (default `1`)
- `KALSHI_ARB_TUNE_SWEEP_TARGET_MAX_PLACED` (default `6`)
- `KALSHI_ARB_TUNE_SWEEP_COOLDOWN_S` (default `7200`)
- `KALSHI_ARB_TUNE_SWEEP_DRY_COOLDOWN_S` (default `900`, used when dry in paper mode)
- `KALSHI_ARB_TUNE_PAPER_MIN_EDGE_BPS_FLOOR` (default `70`, paper-only)
- `KALSHI_ARB_TUNE_PAPER_MIN_LIQUIDITY_USD_FLOOR` (default `5`, paper-only)
- `KALSHI_ARB_TUNE_PAPER_MIN_SECONDS_TO_EXPIRY_FLOOR` (default `180`, paper-only)
- `KALSHI_ARB_IGNORE_ZERO_LIQUIDITY` (default `0`; if `1`, treat liquidity `<=0` as unknown instead of auto-reject)
- `KALSHI_ARB_REINVEST_MAX_FRACTION` (default `0.08`, can be auto-tuned in paper mode on budget pressure)
- `KALSHI_ARB_DRY_STREAK_LOOSEN_STEP_BPS` (default `10`)
- `KALSHI_ARB_DRY_STREAK_LOOSEN_EVERY_CYCLES` (default `18`)
- `KALSHI_ARB_LOOSEN_FLOOR_EDGE_BPS` (default `85`)

Dryness/stuck observability knobs:
- `KALSHI_ARB_SERIES_ROTATION_ENABLED` (default `1`)
- `KALSHI_ARB_SERIES_ROTATION_DRY_ROUNDS` (default `3`)
- `KALSHI_ARB_SERIES_ROTATION_MIN_BLOCKER_SHARE` (default `0.60`)
- `KALSHI_ARB_SERIES_FALLBACKS` (default `KXETH`)
- `KALSHI_ARB_STUCK_ENABLED` (default `1`)
- `KALSHI_ARB_STUCK_WINDOW_S` (default `86400`)
- `KALSHI_ARB_STUCK_MIN_CYCLES` (default `24`)
- `KALSHI_ARB_STUCK_DOMINANT_BLOCKER_SHARE` (default `0.70`)

Aggressive expansion knobs (paper-first):
- `KALSHI_ARB_SERIES` (can include `KXBTCD,KXETHD,KXBTC15M,KXETH15M,KXSOL15M,KXXRP15M`)
- `KALSHI_ARB_SERIES_STRUCTURAL` (for structural modules, e.g. `KXBTCMAXMON,KXBTCMINMON,KXETHMAXMON,KXSOLMAXMON`)
- `KALSHI_ARB_REQUIRE_MAPPED_SERIES` (default `1`; refuse unmapped series)
- `KALSHI_ARB_ENABLE_STRIKE_MONO_ARB` (default `1`)
- `KALSHI_ARB_ENABLE_TIME_MONO_ARB` (default `1`)
- `KALSHI_ARB_ENABLE_TOUCH_LADDER_ARB` (default `1`)
- `KALSHI_ARB_STRUCT_MIN_EDGE_BPS` (default `220`)
- `KALSHI_ARB_STRUCT_MIN_LIQUIDITY_USD` (default `25`)
- `KALSHI_ARB_ROUTER_ENABLED` (default `1`)
- `KALSHI_ARB_ROUTER_MAX_SERIES_SHARE` (default `0.35`)
- `KALSHI_ARB_ROUTER_MIN_OBS` (default `12`)

---

## kalshi_digest.py

### Purpose
Send a concise Telegram digest summarizing the last N hours of Kalshi arb activity:
- cycles, live orders, errors
- notional/cash/MTM summary
- kill switch state
- autotune champion/challenger status
- TCA rollups (slippage/fees), including variant split when available
- settlement attribution diagnostics (match-rate + unmatched window/total)

### Usage

```bash
python3 scripts/kalshi_digest.py --window-hours 8 --send
```

---

## kalshi_digest_reliability.py

### Purpose
Monitor Kalshi digest email delivery reliability by correlating:
- OpenClaw cron run history for `kalshi-ref-arb-digest`
- AgentMail sent-message history for the Kalshi digest recipient

It supports:
- Morning guard: alert when the 07:00 ET run is `ok` but no email is observed
  within 10 minutes.
- Daily report: summarize expected slots (`07:00`, `15:00`, `23:00`) vs actual
  sent emails.

### Usage

Guard + daily report (default behavior when no mode flags are passed):

```bash
python3 scripts/kalshi_digest_reliability.py
```

Guard only (with Telegram alerts):

```bash
python3 scripts/kalshi_digest_reliability.py --guard --send-telegram
```

Daily report only (with Telegram alerts):

```bash
python3 scripts/kalshi_digest_reliability.py --daily-report --send-telegram
```

State is persisted at:
- `tmp/kalshi_ref_arb/digest_delivery_monitor_state.json`

---

## polymarket_sports_paper.py

### Purpose
Paper-only Polymarket sports arb module (separate from crypto bot):
- scans active **sports** binary markets
- checks paired opportunities:
- `YES(A)+YES(B) < threshold` (default `0.98`)
- `NO(A)+NO(B) < threshold` (NO side proxied from top bids)
- simulates near-simultaneous paired execution with FOK-style semantics
- enforces independent paper risk caps and persists a local ledger

### Usage

```bash
python3 scripts/polymarket_sports_paper.py scan
python3 scripts/polymarket_sports_paper.py trade
python3 scripts/polymarket_sports_paper.py status
```

Notes:
- This module is hard paper-only. Passing `--allow-write` returns `paper_only_module`.
- Artifacts/ledger live under `tmp/polymarket_sports_paper/`.

---

## polymarket_sports_paper_cycle.py

### Purpose
Single-cycle runner for unattended paper sports execution:
- runs `polymarket_sports_paper.py trade`
- writes artifacts to `tmp/polymarket_sports_paper/runs/`
- updates `tmp/polymarket_sports_paper/last_cycle_status.json`
- optionally notifies Telegram on errors only

### Usage

```bash
python3 scripts/polymarket_sports_paper_cycle.py
```

### Key Env Knobs

- `PM_SPORTS_PAPER_LIMIT` (default `30`)
- `PM_SPORTS_PAPER_MAX_PAGES` (default `2`)
- `PM_SPORTS_PAPER_TIMEOUT_S` (default `120`)
- `PM_SPORTS_PAPER_LOCK_STALE_SEC` (default `600`)
- `PM_SPORTS_PAPER_NOTIFY_ERRORS` (default `1`)
- `PM_SPORTS_PAPER_ERROR_NOTIFY_COOLDOWN_S` (default `900`)

Notes:
- Cycle overlap is prevented with a lock at `tmp/polymarket_sports_paper/cycle.lock`.
- If a prior cycle is still running, status is recorded as `skipped_lock` (not an error).
