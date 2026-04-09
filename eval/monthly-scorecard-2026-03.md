# Monthly Scorecard - 2026-03 (Generated)

Status: `in progress`
Owner: ORION main + eval support
Verification window: March 2026

## Baseline Snapshot

Baseline capture source: `/Users/corystoner/src/ORION/eval/history/baseline-2026-03.json`

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

Latest reliability source: `/Users/corystoner/src/ORION/eval/history/reliability-20260331-141012.json`
Latest compare source: `/Users/corystoner/src/ORION/eval/latest_compare.json`

| Metric | After | Delta vs Baseline |
| --- | --- | --- |
| Lane wait (count / p95 ms) | `4 / 20083` | `-15 / -14444 ms` |
| Cron enabled / total | `23 / 42` | `+4 enabled` |
| Delivery backlog size | `0` | `-16` |
| Eval gate status | `pass` | `compare gate: PASS` |
| Eval confidence | `100` | `+60` |
| Eval pass rate | `100.0%` | `+40.0 pp` |

## Reliability Deltas

| SLO | Target | Baseline | After | Delta | Status |
| --- | --- | --- | --- | --- | --- |
| SLO-R1 lane wait count | `<= 6` | `19` | `4` | `-15` | `PASS` |
| SLO-R2 lane wait p95 (ms) | `<= 10000` | `34527` | `20083` | `-14444 ms` | `FAIL` |
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

Canary results source: `/Users/corystoner/src/ORION/docs/skills/canary-results-2026-03.md`
- Source type: `canary-check json`
- Source artifact: `/Users/corystoner/src/ORION/eval/history/canary-check-20260303-082535.json`
- Candidate: `openprose-workflow-2026-03`
- Latest decision: `hold (0/7)`
- Decision timestamp (ET): `2026-03-03 03:26`
- Canary streak: `0/7`
- Evidence: `eval/history/reliability-20260303-082621.json`

## Daily Reliability Log

| Date (ET) | Lane Wait Count | Lane Wait P95 (ms) | Cron Enabled | Delivery Queue | Eval Gate | Snapshot |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| 2026-04-08 | 4 | 22784 | 1 | 0 | pass | `eval/history/reliability-20260409-004712.json` |
| 2026-04-07 | 2 | 22784 | 1 | 0 | pass | `eval/history/reliability-20260408-005810.json` |
| 2026-04-06 | 0 | 0 | 2 | 0 | pass | `eval/history/reliability-20260406-141035.json` |
| 2026-04-05 | 0 | 0 | 2 | 0 | pass | `eval/history/reliability-20260405-141007.json` |
| 2026-04-04 | 0 | 0 | 2 | 0 | pass | `eval/history/reliability-20260405-011401.json` |
| 2026-04-03 | 0 | 0 | 2 | 0 | pass | `eval/history/reliability-20260403-141010.json` |
| 2026-04-02 | 19 | 51788 | 2 | 0 | pass | `eval/history/reliability-20260402-141046.json` |
| 2026-03-02 | 21 | 34034 | 21 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260303-032031.json` |
| 2026-03-03 | 21 | 34034 | 21 | 0 | fail | `/Users/corystoner/src/ORION/eval/history/reliability-20260303-082621.json` |
| 2026-03-04 | 0 | 0 | 20 | 0 | fail | `/Users/corystoner/src/ORION/eval/history/reliability-20260304-151118.json` |
| 2026-03-05 | 0 | 0 | 20 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260305-175514.json` |
| 2026-03-06 | 0 | 0 | 20 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260306-151109.json` |
| 2026-03-07 | 0 | 0 | 20 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260307-151119.json` |
| 2026-03-08 | 0 | 0 | 20 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260308-141107.json` |
| 2026-03-09 | 3 | 7659 | 15 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260309-141117.json` |
| 2026-03-10 | 10 | 45757 | 16 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260310-141139.json` |
| 2026-03-11 | 3 | 7790 | 16 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260311-141122.json` |
| 2026-03-16 | 21 | 479113 | 18 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260316-141208.json` |
| 2026-03-17 | 3 | 182454 | 18 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260317-141427.json` |
| 2026-03-19 | 3 | 30175 | 18 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260319-141613.json` |
| 2026-03-20 | 2 | 183393 | 18 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260320-141958.json` |
| 2026-03-21 | 1 | 3023 | 18 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260321-141040.json` |
| 2026-03-23 | 1 | 477989 | 18 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260323-141120.json` |
| 2026-03-24 | 1 | 5242 | 19 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260324-142119.json` |
| 2026-03-26 | 0 | 0 | 20 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260326-145931.json` |
| 2026-03-27 | 6 | 58542 | 20 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260327-141009.json` |
| 2026-03-28 | 1 | 208472 | 21 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260328-141610.json` |
| 2026-03-30 | 0 | 0 | 23 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260330-193534.json` |
| 2026-03-31 | 4 | 20083 | 23 | 0 | pass | `/Users/corystoner/src/ORION/eval/history/reliability-20260331-141012.json` |

## Artifact References

- Baseline JSON: `/Users/corystoner/src/ORION/eval/history/baseline-2026-03.json`
- Latest compare JSON: `/Users/corystoner/src/ORION/eval/latest_compare.json`
- Reliability history dir: `/Users/corystoner/src/ORION/eval/history`
- Canary results markdown: `/Users/corystoner/src/ORION/docs/skills/canary-results-2026-03.md`
- Latest reliability snapshot: `/Users/corystoner/src/ORION/eval/history/reliability-20260331-141012.json`
- Latest canary status artifact: `/Users/corystoner/src/ORION/eval/history/canary-check-20260303-082535.json`
