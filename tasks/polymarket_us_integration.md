# Polymarket US Integration (Scaffold)

Owner: ORION
Copilot(s): LEDGER (cost/risk), STRATUS (ops), WIRE (docs fidelity)
Status: scaffolding

## Goal
Add Polymarket US as a first-class venue alongside Kalshi:
- Phase 1: read-only health + market-data access (safe).
- Phase 2: authenticated portfolio visibility (balances/positions) with Ed25519 signing.
- Phase 3: trading (orders/cancels) behind explicit `ALLOW_WRITE` + risk gates.
- Phase 4: arb logic (intra-venue YES+NO < $1, and later cross-venue vs Kalshi where mapping exists).

## Dependency Graph
- T1 Docs + auth constraints
  depends_on: []
- T2 REST client (market-data + authed endpoints)
  depends_on: [T1]
- T3 Probe CLI + run artifacts
  depends_on: [T2]
- T4 Ledger plumbing
  depends_on: [T2, T3]
- T5 Strategy adapters (arb signals)
  depends_on: [T2, T4]
- T6 Cron + digest surface area
  depends_on: [T3, T4]
- T7 Trading enablement (explicit, gated)
  depends_on: [T5, T6]

## LEDGER Review Questions (when moving to trading)
- What is the initial capital budget earmarked for PM-US? (separate from Kalshi)
- What is acceptable max downside per day + per market?
- What failure modes are acceptable (API down, partial fills, stale orderbook)?
- Are we funding onchain (USDC) or using offchain balances only?

## Notes
- Polymarket US Retail API uses Ed25519 signatures in headers.
- ORION should treat PM-US as experimental until it runs cleanly for 1-2 weeks read-only.

