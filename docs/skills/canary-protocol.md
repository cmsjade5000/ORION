# Staged Canary Protocol (Skills)

Last updated: 2026-03-02
Policy status: Mandatory for all new or materially changed skills.

## Objective

Provide a decision-complete process for introducing a skill with measurable safety and reliability gates before production promotion.

## Preconditions

All must be true before starting canary:
- Candidate has passed intake criteria in `docs/skills/skill-intake-rubric.md`.
- Candidate appears in active shortlist at `docs/skills/shortlist-2026-03-weekly.md`.
- Rollback steps are documented and command-tested in staging.
- Evaluation owner and backup owner are assigned.

## Stage 0: Staging Install (No Production Traffic)

1. Record candidate ID, version/commit SHA, and install timestamp.
2. Install only in staging workspace/runtime context.
3. Keep production config unchanged.
4. Capture install proof (commands + outputs) in results log.

Suggested record fields:
- Skill name
- Source URL
- Pinned version/commit
- Installer
- Staging target environment
- Install command transcript path

## Stage 1: Pre-Canary Baseline Eval

Run baseline evaluations before enabling the candidate:
- Reliability baseline (same scenarios candidate will touch).
- Quality baseline (task success/accuracy for target workflows).
- Safety baseline (policy and forbidden-action checks).

Required outputs:
- Baseline metric snapshot with timestamp.
- Command transcript paths.
- Known caveats or unstable fixtures.

If baseline data is missing, stop and mark status `pending verification`.

## Stage 2: Canary Enablement

1. Enable candidate only in staging with explicit feature flag/scope.
2. Execute planned canary test cases from shortlist test plan.
3. Run post-change eval suite on identical scenarios used for baseline.
4. Log deltas for all monitored metrics.

One-shot staged harness command:

```bash
make canary-stage \
  CANDIDATE=openprose-workflow-2026-03 \
  STAGE_CMD='echo stage-ok' \
  ROLLBACK_CMD='echo rollback-ok'
```

## SLO Gates (Must Pass)

Canary fails immediately if any gate is violated:
- Reliability gate: no increase in failed task executions greater than 2% absolute versus baseline.
- Latency gate: p95 latency regression no worse than 10% versus baseline.
- Safety gate: zero policy-violating actions or forbidden side effects.
- Observability gate: required logs/events present for at least 99% of canary test runs.
- Error budget gate: no unhandled critical errors during canary window.

Any failed gate requires rollback and incident note.

## Rollback Procedure

1. Disable candidate feature flag/scope in staging immediately.
2. Remove or revert candidate to last known-good version.
3. Re-run critical smoke tests to confirm recovery.
4. Log rollback timestamp, trigger condition, and verification evidence.
5. Set candidate status to `hold` or `rejected` until root cause is documented.

Rollback must be executable without destructive data resets.

## Promotion Criteria (7-Day Gate)

Promote from canary to broader rollout only when all are true:
- Seven consecutive days completed in canary.
- All SLO gates passed throughout the period.
- No unresolved `pending verification` evidence items.
- Post-canary eval is neutral-or-better against baseline on agreed success metrics.
- Explicit reviewer sign-off recorded with date.

If seven full days have not elapsed, status remains `in progress`.

## Forbidden Actions

- No direct production install before canary completion.
- No bypass of intake scoring or source validation.
- No unpinned version installs for canary candidates.
- No secret material in docs, logs, or evidence links.
- No destructive cleanup/reset as part of rollback.
- No claim of success without attached verification evidence.

## Required Logging Location

Use `docs/skills/canary-results-2026-03.md` for canary run records and status updates.
