# Kalshi Crypto Reference Arb Bot (US Execution)

This bot is designed for the setup you described:
- **Live trading from the US**
- **Execution venue:** Kalshi
- **Reference prices:** Coinbase + Kraken spot, with Binance read-only quotes enabled by default for cross-venue diagnostics unless `KALSHI_ARB_REF_FEEDS` overrides it

This is not strict “arb” against another prediction market. It is:
- “Kalshi mispricing vs a reference-implied fair probability model”
- optionally with **external hedging later** (not implemented yet)

## What It Trades (Initial Scope)

Kalshi binary markets that expose:
- `strike_type` in `{greater, less, between}`
- a numeric strike (`floor_strike` for `greater`, `cap_strike` for `less`, both for `between`)
- a known expiration timestamp (`expected_expiration_time`)

Example: Bitcoin markets under series like `KXBTC`.

## Model (Initial)

Fair probability uses a simple lognormal approximation:
- spot `S` from the configured read-only reference feeds
- strike `K` from Kalshi
- time-to-expiry `T`
- volatility `sigma_annual` (configurable)

Then:
- `P(S_T > K) ~= N(d2)` with `d2 = (ln(S/K) - 0.5*sigma^2*T) / (sigma*sqrt(T))`

Notes:
- Kalshi resolves crypto markets off CF Benchmarks indexes; Coinbase/Kraken is an approximation.
- Default feed selection is `coinbase,kraken,binance`; override with `KALSHI_ARB_REF_FEEDS` if you want a narrower feed set.
- This is a starting point. For production-grade signals you’ll want options/perp-implied distributions.

## Tracking (Positions / Fills / Settlements)

The cycle runner captures a post-trade portfolio snapshot each run (best-effort):
- balance
- open positions
- recent orders, fills, settlements

This enables closed-loop monitoring without manual intervention and powers the digest.

## Files

- `scripts/kalshi_ref_arb.py` CLI
- `scripts/arb/kalshi.py` Kalshi API client (unauth + auth)
- `scripts/arb/exchanges.py` Coinbase/Kraken price fetch
- `scripts/arb/prob.py` probability math
- `scripts/arb/risk.py` risk checks + local state

## Usage

Read-only scan (no credentials required):

```bash
python3 scripts/kalshi_ref_arb.py scan --series KXBTC --limit 10
```

Trade mode defaults to dry-run unless `--allow-write` is set:

```bash
python3 scripts/kalshi_ref_arb.py trade --series KXBTC --limit 10
```

Runtime healthcheck (config + optional auth):

```bash
python3 scripts/kalshi_ref_arb.py healthcheck
python3 scripts/kalshi_ref_arb.py healthcheck --check-auth
```

Enable live order placement (requires credentials + explicit flag):

```bash
KALSHI_API_KEY_ID=... \\
KALSHI_PRIVATE_KEY_PATH=/path/to/kalshi-key.pem \\
python3 scripts/kalshi_ref_arb.py trade --series KXBTC --limit 10 --allow-write
```

## Secrets / Credentials

Do not store secrets in this repo.

Use:
- `KALSHI_API_KEY_ID` (public key id)
- `KALSHI_PRIVATE_KEY_PATH` (private key PEM path)

These should live under your local secret management per `KEEP.md`.

## Stop Gates

Before enabling `--allow-write`:
- confirm Kalshi account funded, permissions correct
- set conservative risk caps (`--max-*` flags)
- create a kill switch file path you can toggle quickly

The bot will refuse writes if a kill-switch file exists (see CLI `--kill-switch-path`).

## Paper-First Safety Gate

Cycle runner now defaults to paper mode unless explicitly armed:

- `KALSHI_ARB_EXECUTION_MODE=paper|live` (default: `paper`)
- `KALSHI_ARB_LIVE_ARMED=0|1` (must be `1` with `live` to send writes)

This means cron can run continuously without accidentally placing live orders.

## Read-Only Reference Feed Controls

- `KALSHI_ARB_REF_FEEDS=coinbase,kraken,binance` (read-only)
- `KALSHI_ARB_ENABLE_FUNDING_FILTER=1`
- `KALSHI_ARB_ENABLE_REGIME_FILTER=1`
- `KALSHI_ARB_MAX_REF_QUOTE_AGE_SEC=3.0`
- `KALSHI_ARB_MAX_REF_DISPERSION_BPS=35` (legacy alias still accepted: `KALSHI_ARB_MAX_DISPERSION_BPS`)
- `KALSHI_ARB_MAX_VOL_ANOMALY_RATIO=1.8`
- `KALSHI_ARB_FUNDING_ABS_BPS_MAX=3.0`

These filters reduce low-quality entries during unstable regimes.

Dynamic edge / sizing controls:
- `KALSHI_ARB_DYNAMIC_EDGE_ENABLED=1`
- `KALSHI_ARB_DYNAMIC_EDGE_REGIME_MULTS=calm:0.9,normal:1.0,hot:1.2`
- `KALSHI_ARB_REINVEST_ENABLED=1`
- `KALSHI_ARB_REINVEST_MAX_FRACTION=0.08`
- `KALSHI_ARB_DRAWDOWN_THROTTLE_PCT=5.0`
- `KALSHI_ARB_PORTFOLIO_ALLOCATOR_ENABLED=1`
- `KALSHI_ARB_PORTFOLIO_ALLOCATOR_MIN_SIGNAL_FRACTION=0.05`
- `KALSHI_ARB_PORTFOLIO_ALLOCATOR_EDGE_POWER=1.0`
- `KALSHI_ARB_PORTFOLIO_ALLOCATOR_CONFIDENCE_POWER=1.0`

Paper execution emulator (paper mode only):
- `KALSHI_ARB_PAPER_EXEC_EMULATOR=1`
- `KALSHI_ARB_PAPER_EXEC_LATENCY_MS=250`
- `KALSHI_ARB_PAPER_EXEC_SLIPPAGE_BPS=5`

Optional live paired hedge:
- `KALSHI_ARB_PAIRED_HEDGE=1`
- `KALSHI_ARB_PAIRED_MIN_PROFIT_BPS=50`

When enabled, the hedge leg is only attempted after the primary live order is confirmed filled or explicitly reported as executed, and it still respects the hard run/market/cash/concentration budget checks.

## Reliability / Ops Knobs

- `KALSHI_ARB_RETRY_MAX_ATTEMPTS=4`
- `KALSHI_ARB_RETRY_BASE_MS=250`
- `KALSHI_ARB_MILESTONE_NOTIFY=1` (milestone/error style Telegram updates only)
- `KALSHI_ARB_METRICS_ENABLED=1`
- `KALSHI_ARB_METRICS_PATH=tmp/kalshi_ref_arb/metrics.prom`

Metrics file is emitted in Prometheus textfile format each cycle.

## Governance: LEDGER Risk Gate

Execution ownership split:
- Routine Kalshi operations/diagnostics: ATLAS -> STRATUS/PULSE.
- Financial policy/risk/parameter changes: LEDGER gate required before ATLAS execution.

For any policy/risk/parameter packet:
- Include LEDGER recommendation (`approve`, `approve_with_limits`, or `defer`).
- Include explicit guardrails (drawdown stop, sizing cap, concentration limits).
- Add `Approval Gate: LEDGER_RESULT_REQUIRED` and `Gate Evidence:` in the execution Task Packet.

## Sizing / Concentration

- `KALSHI_ARB_MAX_MARKET_CONCENTRATION_FRACTION=0.35`

Caps per-ticker notional concentration relative to bankroll/cycle budget.
Allocator mode pre-distributes cycle notional across candidate tickers by edge/confidence,
then still enforces the same per-market/per-run and concentration hard caps.

## Autotune Visibility

`tmp/kalshi_ref_arb/tune_state.json` now tracks:
- `champion` params/metrics (current baseline policy)
- `challenger` params/metrics (currently evaluated policy)
- `active_variant` and eval progress

Digest output surfaces this plus TCA by variant (champion vs challenger) to make
promotion/rollback decisions auditable.

## Ledger Attribution Diagnostics

`tmp/kalshi_ref_arb/closed_loop_ledger.json` now includes attribution diagnostics:
- `attribution_stats.attempted|matched|unmatched|partial_matches|last_ts`
- settlement records are incremental (`events`) and support partial fills
- per-order settlement carries `settled_count_total`, `filled_count`, and `fully_settled`

Closed-loop reports and digest payloads now surface:
- settlement attribution match-rate
- unmatched settlements (window + total)
- closed-loop `by_variant` (champion/challenger) performance breakdown

## Paper Backtest Harness

Use closed-loop ledger data with configurable fee/slippage assumptions:

```bash
python3 scripts/kalshi_backtest.py --window-hours 336 --fee-bps 5 --slippage-bps 8 --walk-forward-folds 4
```

## Autopilot (ORION, Every 5 Minutes)

This repo includes a deterministic cycle runner:
- `scripts/kalshi_autotrade_cycle.py`

It runs:
1. `balance` (auth + funds check)
2. `trade --allow-write` (still guarded by kill switch + caps)
3. Writes artifacts under `tmp/kalshi_ref_arb/runs/`
4. Sends a Telegram message only when it places a live order or hits an error (rate-limited).

### Make Credentials Available To The Gateway Service

OpenClaw cron jobs run inside the Gateway environment, not your interactive shell.

You should set these in `~/.openclaw/.env` (local-only per `KEEP.md`) so cron can see them:
- `KALSHI_API_KEY_ID=...`
- `KALSHI_PRIVATE_KEY_PATH=/absolute/path/to/kalshi_key.pem`

Then restart the gateway:

```bash
openclaw gateway restart
```

### Preferred unattended runner

Use the direct LaunchAgent install instead of an OpenClaw cron. This avoids repeated `system.run` approval prompts for the live trading cycle and keeps execution on the local host.

```bash
bash scripts/install_orion_kalshi_autotrade_cycle_launchagent.sh
```

What it does:
- installs `~/Library/LaunchAgents/com.openclaw.orion.kalshi_autotrade_cycle.plist`
- runs `scripts/kalshi_autotrade_cycle_run.sh` every 5 minutes
- runs the freshness check after each cycle
- disables the old `kalshi-ref-arb-5m` OpenClaw cron job if it exists

### Legacy OpenClaw cron path

Do not use this for unattended live trading unless you explicitly want approval-gated execution. This path routes through agent `system.run`, which can surface `Approval required` prompts to Telegram/Discord.

```bash
openclaw cron add \
  --name "kalshi-ref-arb-5m" \
  --description "Kalshi crypto ref arb autotrade cycle (KXBTC). Live trades are capped by conservative per-run/per-market limits and kill switch." \
  --cron "*/5 * * * *" \
  --tz "America/New_York" \
  --agent main \
  --session isolated \
  --no-deliver \
  --wake "next-heartbeat" \
  --message "Run python3 scripts/kalshi_autotrade_cycle.py. Respond NO_REPLY."
```

If you already created this cron, disable it after installing the LaunchAgent:

```bash
openclaw cron list --all --json | jq -r '.jobs[] | select(.name == "kalshi-ref-arb-5m") | .id'
openclaw cron disable <job-id>
```

### Kill Switch

Create this file to stop trading immediately:
- `tmp/kalshi_ref_arb.KILL`

## Telegram Digest (Fixed Times, Pittsburgh)

Add a digest cron that sends a short status summary at:
- 7:00 AM ET
- 3:00 PM ET
- 11:00 PM ET

(Timezone: `America/New_York`.)

```bash
openclaw cron add \
  --name "kalshi-ref-arb-digest" \
  --description "Kalshi ref arb Telegram digest at 7am/3pm/11pm America/New_York (8h window)" \
  --cron "0 7,15,23 * * *" \
  --tz "America/New_York" \
  --agent main \
  --session isolated \
  --no-deliver \
  --wake "next-heartbeat" \
  --message "Run python3 scripts/kalshi_digest.py --window-hours 8 --send. Respond NO_REPLY."
```
