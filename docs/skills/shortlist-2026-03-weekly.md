# Weekly Skill Shortlist (March 2026)

Last updated: 2026-03-30
Cadence: Weekly refresh (keep this file rolling through March 2026).
Policy: Any candidate that survives intake must follow staged canary in `docs/skills/canary-protocol.md`.

## How to Use

1. Add or update candidate rows during weekly review.
2. Link hard evidence before changing status from `researching` to `intake-ready`.
3. Do not promote to production directly from this sheet.
4. Keep decision notes short and link deeper artifacts.

## Candidate Table

| Week Of | Candidate Skill | Source | Capability Hypothesis | Evidence Links | Expected ROI | Test Plan | Intake Score | Status | Owner |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| 2026-03-02 | OpenProse workflow canary | Official OpenClaw docs | Structured research-and-drafting workflows for higher-quality, repeatable outputs | `https://docs.openclaw.ai/prose` | Reduce rerun/edit loops for long-form packets | Compare task completion quality and turnaround with/without prose flow | `[pending]` | researching | ORION |
| 2026-03-02 | Gmail PubSub usage pattern | Official OpenClaw docs | Lower-latency email-trigger workflows with fewer polling cycles | `https://docs.openclaw.ai/channels/gmail` | Lower cron polling load and faster event ingestion | Stage one mailbox flow and compare latency/error profile | `[pending]` | researching | ORION |

## Weekly Review Checklist

- Intake rubric scored in `docs/skills/skill-intake-rubric.md`.
- Source validation complete for online-discovered skills.
- Risks and rollback constraints documented before canary start.
- Pre/post evaluation plan attached for each `intake-ready` candidate.

## Status Definitions

- `researching`: Candidate identified; evidence incomplete.
- `intake-ready`: Intake score complete and eligible for staging.
- `canary-running`: Installed in staging and under gated observation.
- `hold`: Blocked by risk, observability, or unresolved evidence gap.
- `rejected`: Removed from consideration.
- `promoted`: Passed 7-day canary gate and approved for wider rollout.

## Automated Discovery (Generated)

- Generated at (ET): `2026-03-30 15:41`
- Sources: `https://docs.openclaw.ai/sitemap.xml, https://github.com/openclaw/openclaw/releases.atom`
- Limit: `8`
- JSON artifact: `eval/history/skills-discovery-20260330-194152.json`
- Markdown artifact: `eval/history/skills-discovery-20260330-194152.md`

| Source | Capability | Risk | Expected ROI | Test Plan | Trust Score | Fit Score | Intake Score | Status |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| docs: [cli/health](https://docs.openclaw.ai/cli/health) | Runtime observability and diagnostics | Low blast radius; main risk is incomplete signal coverage. | Faster triage and clearer promotion/rollback gating evidence. | Inject controlled failure in staging and confirm logs, metrics, and alerts capture it. | 5.0 | 4.1 | 91.9 | intake-ready |
| docs: [gateway/health](https://docs.openclaw.ai/gateway/health) | Runtime observability and diagnostics | Low blast radius; main risk is incomplete signal coverage. | Faster triage and clearer promotion/rollback gating evidence. | Inject controlled failure in staging and confirm logs, metrics, and alerts capture it. | 5.0 | 4.1 | 91.9 | intake-ready |
| docs: [automation/gmail-pubsub](https://docs.openclaw.ai/automation/gmail-pubsub) | Automation trigger orchestration | Trigger misconfiguration can create duplicate or noisy executions. | Lower polling overhead and faster event-to-action latency. | Stage one trigger in sandbox, replay sample events, compare latency and errors. | 5.0 | 4.8 | 87.2 | intake-ready |
| docs: [automation/webhook](https://docs.openclaw.ai/automation/webhook) | Automation trigger orchestration | Trigger misconfiguration can create duplicate or noisy executions. | Lower polling overhead and faster event-to-action latency. | Stage one trigger in sandbox, replay sample events, compare latency and errors. | 5.0 | 4.8 | 87.2 | intake-ready |
| docs: [prose](https://docs.openclaw.ai/prose) | Workflow quality and output structure | Higher process complexity can increase runtime cost if over-applied. | Improve output consistency and reduce rerun/edit loops. | A/B test representative tasks for quality score, revision count, and turnaround. | 5.0 | 4.4 | 86.8 | intake-ready |
| docs: [concepts/system-prompt](https://docs.openclaw.ai/concepts/system-prompt) | Workflow quality and output structure | Higher process complexity can increase runtime cost if over-applied. | Improve output consistency and reduce rerun/edit loops. | A/B test representative tasks for quality score, revision count, and turnaround. | 5.0 | 4.0 | 85.2 | intake-ready |
| release: [openclaw 2026.3.28](https://github.com/openclaw/openclaw/releases/tag/v2026.3.28) | Core runtime upgrade candidate | Release changes can introduce regressions without staged validation. | Adopt upstream fixes and capabilities with lower long-term drift. | Pin release in staging, run regression suite, compare reliability metrics, confirm rollback. | 5.0 | 4.4 | 82.6 | intake-ready |
| release: [openclaw 2026.3.24](https://github.com/openclaw/openclaw/releases/tag/v2026.3.24) | Core runtime upgrade candidate | Release changes can introduce regressions without staged validation. | Adopt upstream fixes and capabilities with lower long-term drift. | Pin release in staging, run regression suite, compare reliability metrics, confirm rollback. | 5.0 | 4.4 | 82.6 | intake-ready |
