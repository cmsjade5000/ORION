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
