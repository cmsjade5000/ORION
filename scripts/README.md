# Scripts

This directory contains maintenance, build, and automation scripts for the Gateway system.

Scripts here are intended to be:
- explicit
- repeatable
- safe to run locally
- version-controlled

Nothing in this directory should modify secrets directly.

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
./scripts/install_orion_miniapp_command_relay_launchagent.sh /Users/corystoner/Desktop/ORION
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

Dryness/stuck observability knobs:
- `KALSHI_ARB_SERIES_ROTATION_ENABLED` (default `1`)
- `KALSHI_ARB_SERIES_ROTATION_DRY_ROUNDS` (default `3`)
- `KALSHI_ARB_SERIES_ROTATION_MIN_BLOCKER_SHARE` (default `0.60`)
- `KALSHI_ARB_SERIES_FALLBACKS` (default `KXETH`)
- `KALSHI_ARB_STUCK_ENABLED` (default `1`)
- `KALSHI_ARB_STUCK_WINDOW_S` (default `86400`)
- `KALSHI_ARB_STUCK_MIN_CYCLES` (default `24`)
- `KALSHI_ARB_STUCK_DOMINANT_BLOCKER_SHARE` (default `0.70`)

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
