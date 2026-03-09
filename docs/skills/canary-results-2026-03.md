# Canary Results Log (March 2026)

Last updated: 2026-03-02
Reference protocol: `/Users/corystoner/src/ORION/docs/skills/canary-protocol.md`

## Current Status

Overall status: `in progress`
Verification status: `pending verification`

Notes:
- Intake and protocol docs prepared.
- Baseline data collection and implementation work are still active.
- No candidate has completed the required 7-day promotion gate.
- Eval gate is currently passing in `/Users/corystoner/src/ORION/eval/scorecard.md`; canary execution may proceed.

### Candidate: `OpenProse workflow canary`

- Candidate ID: `openprose-workflow-2026-03`
- Source URL: `https://docs.openclaw.ai/prose`
- Pinned version/commit: `pending verification`
- Owner: `ORION`
- Start date (ET): `2026-03-02`
- Status: `in progress`
- Verification: `pending verification`

Pre-canary baseline evidence:
- Reliability baseline: `/Users/corystoner/src/ORION/eval/history/baseline-2026-03.json`
- Quality baseline: `/Users/corystoner/src/ORION/eval/scorecard.md`
- Safety baseline: `/Users/corystoner/src/ORION/eval/latest_compare.json`

Canary execution evidence:
- Install transcript: `/Users/corystoner/src/ORION/eval/history/canary-openprose-run1-2026-03-02.json` (staging-only simulated canary run)
- Test run transcript(s): `/Users/corystoner/src/ORION/eval/history/canary-openprose-run1-2026-03-02.md`
- Observability evidence: `/Users/corystoner/src/ORION/eval/history/reliability-20260303-021409.json`

SLO gate outcomes:
- Reliability gate: `pending` (requires sustained multi-day window)
- Latency gate: `pass` (run duration 9355 ms, no timeout/error)
- Safety gate: `pass` (current eval gate passing)
- Observability gate: `pass` (artifacts captured for run + runtime snapshot)
- Error budget gate: `pending`

Decision:
- Promotion eligibility: `not eligible`
- 7-day gate complete: `no`
- Reviewer sign-off: `pending`
- Comments: `Canary run #1 completed with no side effects; continue daily canary evidence collection.`

## Run Ledger Template

Use one block per candidate canary attempt.

### Candidate: `<skill-name>`

- Candidate ID: `<id>`
- Source URL: `<url>`
- Pinned version/commit: `<version-or-sha>`
- Owner: `<owner>`
- Start date (ET): `<YYYY-MM-DD>`
- Status: `queued | in progress | rollback | hold | rejected | promoted`
- Verification: `pending verification | verified`

Pre-canary baseline evidence:
- Reliability baseline: `<link/path>`
- Quality baseline: `<link/path>`
- Safety baseline: `<link/path>`

Canary execution evidence:
- Install transcript: `<link/path>`
- Test run transcript(s): `<link/path>`
- Observability evidence: `<link/path>`

SLO gate outcomes:
- Reliability gate: `pass/fail` (delta: `<value>`)
- Latency gate: `pass/fail` (delta: `<value>`)
- Safety gate: `pass/fail` (notes: `<value>`)
- Observability gate: `pass/fail` (coverage: `<value>`)
- Error budget gate: `pass/fail` (notes: `<value>`)

Decision:
- Promotion eligibility: `not eligible | eligible`
- 7-day gate complete: `no | yes`
- Reviewer sign-off: `<name/date or pending>`
- Comments: `<summary>`

## Weekly Summary Template

| Week Ending | Candidate | Days in Canary | SLO Status | Decision | Notes |
| --- | --- | ---: | --- | --- | --- |
| 2026-03-09 | OpenProse workflow canary | 1 | Partial pass (reliability pending) | continue | First staging run completed; eval gate pass retained. |
| `<YYYY-MM-DD>` | `<skill-name>` | `<0-7+>` | `<pass/fail/pending>` | `<continue/rollback/hold/promote>` | `<summary>` |

## Automated Canary Checks

| Timestamp (ET) | Candidate | Eval Gate | Lane Wait Count | Lane Wait P95 (ms) | Delivery Queue | Decision | Evidence |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| 2026-03-03 03:26 | openprose-workflow-2026-03 | fail | 21 | 34034 | 0 | hold (0/7) | `eval/history/reliability-20260303-082621.json` |
| 2026-03-03 01:26 | openprose-workflow-2026-03 | fail | 21 | 34034 | 0 | hold (0/7) | `eval/history/reliability-20260303-062616.json` |
| 2026-03-02 21:44 | openprose-workflow-2026-03 | pass | 20 | 34527 | 0 | hold (0/7) | `eval/history/reliability-20260303-024229.json` |
| 2026-03-02 21:43 | openprose-workflow-2026-03 | pass | 20 | 34527 | 0 | hold (0/7) | `eval/history/reliability-20260303-024229.json` |
| 2026-03-02 21:42 | openprose-workflow-2026-03 | pass | 20 | 34527 | 0 | hold (0/7) | `eval/history/reliability-20260303-024229.json` |
| 2026-03-02 21:41 | openprose-workflow-2026-03 | pass | 20 | 34527 | 0 | hold (0/7) | `eval/history/reliability-20260303-022934.json` |
| 2026-03-02 21:40 | openprose-workflow-2026-03 | pass | 20 | 34527 | 0 | hold (0/7) | `eval/history/reliability-20260303-022934.json` |
| 2026-03-02 21:29 | openprose-workflow-2026-03 | pass | 20 | 34527 | 0 | continue | `eval/history/reliability-20260303-022934.json` |
| 2026-03-02 21:28 | openprose-workflow-2026-03 | pass | 20 | 34527 | 0 | continue | `eval/history/reliability-20260303-022859.json` |
| 2026-03-02 21:26 | openprose-workflow-2026-03 | pass | 20 | 34527 | 0 | continue | `eval/history/reliability-20260303-022638.json` |
| 2026-03-02 21:24 | openprose-workflow-2026-03 | pass | 20 | 34527 | 0 | continue | `eval/history/reliability-20260303-022457.json` |
| 2026-03-02 21:22 | openprose-workflow-2026-03 | pass | 20 | 34527 | 0 | continue | `eval/history/reliability-20260303-022236.json` |
