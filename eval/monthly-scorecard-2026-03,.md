# Monthly Scorecard - 2026-03, (Generated)

Status: `in progress`
Owner: ORION main + eval support
Verification window: 2026-03,

## Baseline Snapshot

Baseline capture source: `/Users/corystoner/src/ORION/eval/history/baseline-2026-03,.json`

| Metric | Baseline |
| --- | --- |
| Lane wait (count / p95 ms) | `unknown / unknown` |
| Cron enabled / total | `unknown / unknown` |
| Delivery backlog size | `unknown` |
| Eval confidence | `unknown` |
| Eval pass rate | `unknown` (unknown/unknown) |
| Eval safety zeros | `unknown` |
| Captured at | `unknown` |

## After Snapshot

Latest reliability source: `/Users/corystoner/src/ORION/eval/history/reliability-20260319-141613.json`
Latest compare source: `/Users/corystoner/src/ORION/eval/latest_compare.json`

| Metric | After | Delta vs Baseline |
| --- | --- | --- |
| Lane wait (count / p95 ms) | `3 / 30175` | `unknown / unknown` |
| Cron enabled / total | `18 / 37` | `unknown enabled` |
| Delivery backlog size | `0` | `unknown` |
| Eval gate status | `pass` | `compare gate: PASS` |
| Eval confidence | `100` | `unknown` |
| Eval pass rate | `100.0%` | `unknown` |

## Reliability Deltas

| SLO | Target | Baseline | After | Delta | Status |
| --- | --- | --- | --- | --- | --- |
| SLO-R1 lane wait count | `<= 6` | `unknown` | `3` | `unknown` | `PASS` |
| SLO-R2 lane wait p95 (ms) | `<= 10000` | `unknown` | `30175` | `unknown` | `FAIL` |
| SLO-R3 enabled cron to disabled channels/plugins | `0` | `unknown` | `0` | `unknown` | `PASS` |
| SLO-R4 delivery backlog | `<= 0` | `unknown` | `0` | `unknown` | `PASS` |

## Eval Quality Deltas

| SLO | Target | Baseline | Current | Delta | Status |
| --- | --- | --- | --- | --- | --- |
| SLO-E1 confidence | `>= 70` | `40` | `100` | `+60` | `PASS` |
| SLO-E2 pass rate | `>= 80.0%` | `60.0%` | `100.0%` | `+40.0 pp` | `PASS` |
| SLO-E3 safety zeros | `<= 0` | `1` | `0` | `-1` | `PASS` |
| SLO-E4 confidence drop | `>= -10` | `0` | `60` | `60` | `PASS` |
Gate verdict: `PASS`

## Canary Progress

Canary results source: `/Users/corystoner/src/ORION/docs/skills/canary-results-2026-03,.md`
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

## Artifact References

- Baseline JSON: `/Users/corystoner/src/ORION/eval/history/baseline-2026-03,.json`
- Latest compare JSON: `/Users/corystoner/src/ORION/eval/latest_compare.json`
- Reliability history dir: `/Users/corystoner/src/ORION/eval/history`
- Canary results markdown: `/Users/corystoner/src/ORION/docs/skills/canary-results-2026-03,.md`
- Latest reliability snapshot: `/Users/corystoner/src/ORION/eval/history/reliability-20260319-141613.json`
- Latest canary status artifact: `/Users/corystoner/src/ORION/eval/history/canary-check-20260303-082535.json`

## Notes

Artifacts missing/unreadable during generation:
- `missing json: /Users/corystoner/src/ORION/eval/history/baseline-2026-03,.json`
