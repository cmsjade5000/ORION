# Kalshi Crypto Reference Arb Bot (US Execution)

This bot is designed for the setup you described:
- **Live trading from the US**
- **Execution venue:** Kalshi
- **Reference prices:** Coinbase + Kraken spot

This is not strict “arb” against another prediction market. It is:
- “Kalshi mispricing vs a reference-implied fair probability model”
- optionally with **external hedging later** (not implemented yet)

## What It Trades (Initial Scope)

Kalshi binary markets that expose:
- `strike_type` in `{greater, less}`
- a numeric strike (`floor_strike`)
- a known expiration timestamp (`expected_expiration_time`)

Example: Bitcoin markets under series like `KXBTC`.

## Model (Initial)

Fair probability uses a simple lognormal approximation:
- spot `S` from (Coinbase, Kraken)
- strike `K` from Kalshi
- time-to-expiry `T`
- volatility `sigma_annual` (configurable)

Then:
- `P(S_T > K) ~= N(d2)` with `d2 = (ln(S/K) - 0.5*sigma^2*T) / (sigma*sqrt(T))`

Notes:
- Kalshi resolves crypto markets off CF Benchmarks indexes; Coinbase/Kraken is an approximation.
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

### Create The Cron Job

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
