# ORION March 2026 SLO Contract

Date: 2026-03-02
Window: March 2026
Scope: Runtime reliability, eval quality, and staged canary safety.

## Baseline Snapshot (Pre-change)

Source: `eval/history/baseline-2026-03.json`

- lane_wait_24h_count: 19
- lane_wait_24h_max_ms: 35296
- lane_wait_24h_p95_ms: 34527
- cron_enabled: 19 / 28 total
- delivery_queue_files: 16 (all stale WhatsApp failures)
- routing eval confidence: 40
- routing eval pass/fail: 6/4
- routing eval safety_zeros: 1
- response latency sample avg: 1924.6 ms
- response latency sample p95: 2179 ms

## SLO Targets

## Reliability
- SLO-R1: `lane_wait_24h_count <= 6`.
- SLO-R2: `lane_wait_24h_p95_ms <= 10000`.
- SLO-R3: enabled cron jobs must not target disabled channels/plugins.
- SLO-R4: delivery queue backlog remains `0` for non-configured channels.

## Eval Quality
- SLO-E1: routing eval confidence `>= 70`.
- SLO-E2: routing eval pass rate `>= 80%`.
- SLO-E3: safety zeros `== 0`.
- SLO-E4: confidence drop vs baseline not lower than `-10`.

## Canary Safety
- SLO-C1: no new unauthorized outbound channel sends.
- SLO-C2: no sustained increase in lane wait violations during canary.
- SLO-C3: 7 consecutive days meeting SLO-R* and SLO-E* before promotion.

## Go / No-Go Gates

Promotion from staging to limited production is blocked if any condition is true:

- Gate-G1: `safety_zeros > 0` in latest eval compare.
- Gate-G2: pass rate below 80%.
- Gate-G3: delivery queue backlog for disabled channels appears.
- Gate-G4: two consecutive daily checks violate SLO-R1 or SLO-R2.

## Daily Monitoring Checklist

- Parse `~/.openclaw/logs/gateway.err.log` for `lane wait exceeded`.
- Validate `~/.openclaw/cron/jobs.json` enabled job channels.
- Check `~/.openclaw/delivery-queue/` backlog count.
- Run `make eval-reliability` to persist the daily runtime snapshot.
- Run `make eval-routing` + `make eval-compare`.
- Record status in `eval/monthly-scorecard-2026-03.md`.
