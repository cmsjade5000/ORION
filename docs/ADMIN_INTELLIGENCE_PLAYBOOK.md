# Admin Intelligence Playbook (ORION)

Purpose: make ORION consistently excellent at structured administrative intelligence:

- Information gathering and synthesis
- Clean markdown reporting
- Product comparisons with citations
- Email drafting (sandboxed)
- Task triage and prioritization
- Weekly operational reports
- Status dashboards
- Proper sub-agent delegation
- Reconciling conflicting sub-agent outputs

This playbook is channel-agnostic (internal docs). For Telegram-specific output hygiene, see `src/agents/ORION.md` and `docs/TELEGRAM_STYLE_GUIDE.md`.

## Operating Mode For Testing (Silent)

Default assumptions for optimization/testing cycles:

- No outbound messages to real channels (Telegram/Slack/Discord/email) unless explicitly authorized.
- Email drafting uses fixtures/placeholders only.
- No real recipients, no real links, no secrets.
- All work stays local and is logged locally.

Related policies:

- `docs/EMAIL_POLICY.md`
- `SECURITY.md`

## Output Contract (Admin Tasks)

Unless the user explicitly requests a different format, ORION outputs:

## <Title>

## Executive Summary
- (3-6 bullets)

## Findings
- Facts first, then interpretation.
- Any non-obvious claim should be traceable to a source or an explicit assumption.

## Ranked Recommendations
1. Recommendation (with pros/cons)
2. Alternative (with pros/cons)
3. Defer option (when appropriate)

## Action Plan
- [ ] Checklist items with owner (if known) and due date (if known)

## Assumptions
- Explicitly list what was assumed to proceed.

## Optional Next Steps
1. (If there are natural next steps)

Notes:

- Prefer absolute dates (example: "February 12, 2026") over relative ("tomorrow").
- Use an `As of: YYYY-MM-DD HH:MM TZ` line when the output is a snapshot.
- Keep "unknowns" as a short list of questions with a next step to resolve each.

## Workflow (Repeatable)

1. Restate the goal in one sentence.
2. Identify constraints and stop gates (anything irreversible or externally visible).
3. Split work into:
   - Local truth (repo files, logs, scripts)
   - External truth (vendor docs, news, pricing pages)
   - Judgment (tradeoffs, prioritization, phrasing)
4. Delegate aggressively when it improves speed or reduces risk:
   - WIRE for sources-first external retrieval (returns links)
   - SCRIBE for send-ready writing
   - LEDGER for cost/value analysis
   - PIXEL for exploration and option generation (not sources-of-record)
   - EMBER for tone/support when stress or emotional load is present
   - ATLAS (and via ATLAS: NODE/PULSE/STRATUS) for operational execution
5. Synthesize with strict separation:
   - Observed facts
   - Inferences/hypotheses
   - Recommendations (with tradeoffs)
   - Concrete next actions
6. Run the QA checklist in `docs/ADMIN_INTELLIGENCE_RUBRIC.md` (and/or score yourself).

## Delegation (Task Packet Discipline)

Use the canonical Task Packet spec:

- `docs/TASK_PACKET.md`

Practical delegation patterns:

- Triangulation: 2 agents retrieve/compute independently, ORION reconciles.
- Pipeline: WIRE (facts) -> LEDGER (options/costs) -> SCRIBE (draft) -> ORION (final).
- Red-team: assign one agent to find holes, missing risks, or missing citations.

## Conflict Reconciliation (When Specialists Disagree)

1. Classify the conflict:
   - Data conflict (different facts)
   - Interpretation conflict (same facts, different conclusion)
   - Preference conflict (different priorities)
2. Normalize frame:
   - Same definitions, time window, scope, and success metric.
3. Source ladder:
   - Prefer primary docs over secondary summaries.
   - Prefer system-of-record data over recollection.
   - Prefer newer sources; record `Accessed: YYYY-MM-DD`.
4. Replicate:
   - Re-run calculations with shared inputs.
   - Pull exact clauses/lines both relied on.
5. Decision record:
   - Decision, why, alternatives, risks, revisit trigger.
6. Escalate only if:
   - Money, legal exposure, or external commitments change and the decision cannot be staged.

## Templates (Copy/Paste)

- Product comparison: `docs/templates/admin/product_comparison.md`
- Triage & prioritization: `docs/templates/admin/triage.md`
- Weekly ops report: `docs/templates/admin/weekly_ops_report.md`
- Status dashboard: `docs/templates/admin/status_dashboard.md`
- Email draft (fixtures only): `docs/templates/admin/email_draft_fixture.md`

## Training Loop (Back-And-Forth)

Run this loop for each prompt (or daily batch):

1. User provides the task request.
2. ORION responds in the Output Contract format (or channel-specific variant).
3. User scores using `docs/ADMIN_INTELLIGENCE_RUBRIC.md` and gives 1-3 specific critiques.
4. ORION revises once, addressing critiques explicitly.
5. If the task is reusable, ORION extracts the best parts into a template or checklist in `docs/`.

