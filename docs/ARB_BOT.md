# Arb Bot (Polymarket) — Safe Read-Only Scanner

This repo includes a **read-only** arb scanner that:
- discovers active Polymarket markets via Gamma
- pulls order books via the Polymarket CLOB API
- detects simple **within-market** YES/NO “buy both” arbitrage when `ask_yes + ask_no < 1` (after fees + a minimum edge)

It is intentionally **not** a live trading bot by default.

## Why Read-Only

1. Safety: automated trading is a write action with real-money consequences.
2. Compliance: Polymarket has geoblocking; the scanner checks geoblock status and refuses live mode.
3. ORION policy: anything that moves funds or places orders must be explicitly confirmed and must not run via the deterministic inbox runner.

## Files

- `scripts/arb_bot.py` main CLI
- `scripts/arb/polymarket.py` Gamma + CLOB clients
- `scripts/arb/arb.py` opportunity detection (pure logic)
- `scripts/arb_scan.sh` safe wrapper (read-only)

## Quick Start (Read-Only)

Run a small scan:

```bash
python3 scripts/arb_bot.py scan --max-markets 10 --min-edge-bps 20
```

Or via the wrapper:

```bash
./scripts/arb_scan.sh --max-markets 10 --min-edge-bps 20
```

Output is JSON to stdout.

## ORION Integration (Inbox Runner)

The inbox runner only executes allowlisted, read-only scripts.

This repo allowlists:
- `arb_scan.sh` (read-only scan)

It does **not** allow any live trading commands.

## Risk Guardrails (Current)

Implemented guardrails:
- live trading is disabled in the CLI (no order placement implemented)
- optional geoblock check (read-only) via `https://polymarket.com/api/geoblock`
- per-run caps (`--max-markets`, `--max-pages`) to avoid hammering APIs
- configurable fee assumptions + min edge threshold

## Extending To Cross-Venue Arbitrage

The current scanner only finds **internal** YES/NO mispricings on Polymarket.

To compare Polymarket vs “exchanges/pms”:
- add a `Venue` adapter for each external venue (Kalshi, CEX odds feed, other PM)
- define market mapping (shared event id / slug mapping)
- expand `scripts/arb/arb.py` to compute executable edge net of fees/slippage

## Stop Gates

Requires Cory confirmation before any of the following:
- storing or rotating any credentials (see `KEEP.md`)
- implementing order placement / signed requests
- enabling any network exposure or background daemon

