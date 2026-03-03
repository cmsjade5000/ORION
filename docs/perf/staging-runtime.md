# Staging Runtime Profile (Skill Canary)

Purpose: isolate canary skill validation from production message paths.

## Profile Rules

- Use isolated sessions for canary test runs.
- Disable outbound delivery for canary runs (`mode=none` or dry-run env flags).
- Keep canary install scope to one skill at a time.
- Run pre and post eval checks around each canary install.

## Required Checks

1. `make eval-routing`
2. `make eval-compare BASE=eval/history/baseline-2026-03.json AFTER=eval/latest_report.json`
3. Verify no growth in delivery queue backlog.
4. Verify no new disabled-channel delivery attempts.

## Promotion Gate

- Only promote if scorecard gate is PASS for 7 consecutive days and reliability SLOs are stable.
