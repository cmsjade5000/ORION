# Memory Index

Last updated: 2026-02-17

## Current Objectives (Top 3)

1. Go live locally on the Mac mini (gateway runtime stable).
2. Verify ORION-only Telegram behavior and inbound DM response.
3. Verify specialist delegation via Task Packets (atlas/node) end-to-end.

## Active Projects

### ORION Gateway Go-Live (Local)

- Status: in progress
- Next step: Verify inbound Telegram DM + ORION-only delivery, then run 1 Task Packet delegation cycle.
- References:
  - `/Users/corystoner/Desktop/ORION/memory/WORKING.md`
  - `/Users/corystoner/Desktop/ORION/TODO.md`

### Kalshi Ops / Autotrade Tooling

- Status: active development (recent high-change area)
- Next step: Keep changes gated behind tests and notional/latency guards; ensure any live-trade intent requires explicit confirmation.
- References:
  - `/Users/corystoner/Desktop/ORION/scripts/kalshi_autotrade_cycle.py`
  - `/Users/corystoner/Desktop/ORION/scripts/kalshi_digest.py`
  - `/Users/corystoner/Desktop/ORION/tests/test_kalshi_analytics.py`

## Operating Constraints (Non-Negotiables)

- ORION is the only Telegram-facing bot (specialists are internal-only).
- Do not commit secrets/tokens. Follow `/Users/corystoner/Desktop/ORION/KEEP.md`.
- Ask before irreversible actions (trades, deletes, rotations).

## Key Decisions (Log)

- 2026-02 (ongoing): Keep stable, long-term notes in `/Users/corystoner/Desktop/ORION/MEMORY.md`; keep transient state in `/Users/corystoner/Desktop/ORION/memory/WORKING.md`.

## Known Issues / Watchlist

- Retrieval/telemetry: limited durable logs in-repo means “retrieval hit rate” is hard to measure.
- Freshness: memory entries do not consistently record “last verified” dates.

## Glossary / Entities

- OpenClaw: agent runtime / gateway system used by ORION.
- Task Packet: structured specialist delegation unit (see `/Users/corystoner/Desktop/ORION/docs/TASK_PACKET.md`).
