# Monthly Scorecard - 2026-03 (Generated)

Status: `in progress`
Owner: ORION main + eval support
Verification window: March 2026

## Baseline Snapshot

Baseline capture source: `/Users/corystoner/Desktop/ORION/eval/history/baseline-2026-03.json`

| Metric | Baseline |
| --- | --- |
| Lane wait (count / p95 ms) | `19 / 34527` |
| Cron enabled / total | `19 / 28` |
| Delivery backlog size | `16` |
| Eval confidence | `40` |
| Eval pass rate | `60.0%` (6/10) |
| Eval safety zeros | `1` |
| Captured at | `2026-03-02T20:50:00-05:00` |

## After Snapshot

Latest reliability source: `/Users/corystoner/Desktop/ORION/eval/history/reliability-20260311-141122.json`
Latest compare source: `/Users/corystoner/Desktop/ORION/eval/latest_compare.json`

| Metric | After | Delta vs Baseline |
| --- | --- | --- |
| Lane wait (count / p95 ms) | `3 / 7790` | `-16 / -26737 ms` |
| Cron enabled / total | `16 / 35` | `-3 enabled` |
| Delivery backlog size | `0` | `-16` |
| Eval gate status | `pass` | `compare gate: PASS` |
| Eval confidence | `100` | `+60` |
| Eval pass rate | `100.0%` | `+40.0 pp` |

## Reliability Deltas

| SLO | Target | Baseline | After | Delta | Status |
| --- | --- | --- | --- | --- | --- |
| SLO-R1 lane wait count | `<= 6` | `19` | `3` | `-16` | `PASS` |
| SLO-R2 lane wait p95 (ms) | `<= 10000` | `34527` | `7790` | `-26737 ms` | `PASS` |
| SLO-R3 enabled cron to disabled channels/plugins | `0` | `unknown` | `0` | `unknown` | `PASS` |
| SLO-R4 delivery backlog | `<= 0` | `16` | `0` | `-16` | `PASS` |

## Eval Quality Deltas

| SLO | Target | Baseline | Current | Delta | Status |
| --- | --- | --- | --- | --- | --- |
| SLO-E1 confidence | `>= 70` | `40` | `100` | `+60` | `PASS` |
| SLO-E2 pass rate | `>= 80.0%` | `60.0%` | `100.0%` | `+40.0 pp` | `PASS` |
| SLO-E3 safety zeros | `<= 0` | `1` | `0` | `-1` | `PASS` |
| SLO-E4 confidence drop | `>= -10` | `0` | `60` | `60` | `PASS` |
Gate verdict: `PASS`

## Canary Progress

Canary results source: `/Users/corystoner/Desktop/ORION/docs/skills/canary-results-2026-03.md`
- Source type: `canary-check json`
- Source artifact: `/Users/corystoner/Desktop/ORION/eval/history/canary-check-20260303-082535.json`
- Candidate: `openprose-workflow-2026-03`
- Latest decision: `hold (0/7)`
- Decision timestamp (ET): `2026-03-03 03:26`
- Canary streak: `0/7`
- Evidence: `eval/history/reliability-20260303-082621.json`

## Daily Reliability Log

| Date (ET) | Lane Wait Count | Lane Wait P95 (ms) | Cron Enabled | Delivery Queue | Eval Gate | Snapshot |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 2026-03-02 | 21 | 34034 | 21 | 0 | pass | `/Users/corystoner/Desktop/ORION/eval/history/reliability-20260303-032031.json` |
| 2026-03-03 | 21 | 34034 | 21 | 0 | fail | `/Users/corystoner/Desktop/ORION/eval/history/reliability-20260303-082621.json` |
| 2026-03-04 | 0 | 0 | 20 | 0 | fail | `/Users/corystoner/Desktop/ORION/eval/history/reliability-20260304-151118.json` |
| 2026-03-05 | 0 | 0 | 20 | 0 | pass | `/Users/corystoner/Desktop/ORION/eval/history/reliability-20260305-175514.json` |
| 2026-03-06 | 0 | 0 | 20 | 0 | pass | `/Users/corystoner/Desktop/ORION/eval/history/reliability-20260306-151109.json` |
| 2026-03-07 | 0 | 0 | 20 | 0 | pass | `/Users/corystoner/Desktop/ORION/eval/history/reliability-20260307-151119.json` |
| 2026-03-08 | 0 | 0 | 20 | 0 | pass | `/Users/corystoner/Desktop/ORION/eval/history/reliability-20260308-141107.json` |
| 2026-03-09 | 3 | 7659 | 15 | 0 | pass | `/Users/corystoner/Desktop/ORION/eval/history/reliability-20260309-141117.json` |
| 2026-03-10 | 10 | 45757 | 16 | 0 | pass | `/Users/corystoner/Desktop/ORION/eval/history/reliability-20260310-141139.json` |
| 2026-03-11 | 3 | 7790 | 16 | 0 | pass | `/Users/corystoner/Desktop/ORION/eval/history/reliability-20260311-141122.json` |

## Artifact References

- Baseline JSON: `/Users/corystoner/Desktop/ORION/eval/history/baseline-2026-03.json`
- Latest compare JSON: `/Users/corystoner/Desktop/ORION/eval/latest_compare.json`
- Reliability history dir: `/Users/corystoner/Desktop/ORION/eval/history`
- Canary results markdown: `/Users/corystoner/Desktop/ORION/docs/skills/canary-results-2026-03.md`
- Latest reliability snapshot: `/Users/corystoner/Desktop/ORION/eval/history/reliability-20260311-141122.json`
- Latest canary status artifact: `/Users/corystoner/Desktop/ORION/eval/history/canary-check-20260303-082535.json`
