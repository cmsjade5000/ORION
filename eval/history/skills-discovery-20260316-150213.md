# Skill Discovery Scan

- Generated at ET: `2026-03-16 11:02`
- Generated at UTC: `2026-03-16T15:02:11.008339+00:00`
- Limit: `8`
- Source count: `345`
- Selected count: `8`
- Sources: `https://docs.openclaw.ai/sitemap.xml, https://github.com/openclaw/openclaw/releases.atom`

## Ranked Candidates

| Source | Capability | Risk | Expected ROI | Test Plan | Trust Score | Fit Score | Intake Score | Status |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| docs: [cli/health](https://docs.openclaw.ai/cli/health) | Runtime observability and diagnostics | Low blast radius; main risk is incomplete signal coverage. | Faster triage and clearer promotion/rollback gating evidence. | Inject controlled failure in staging and confirm logs, metrics, and alerts capture it. | 5.0 | 4.1 | 91.9 | intake-ready |
| docs: [gateway/health](https://docs.openclaw.ai/gateway/health) | Runtime observability and diagnostics | Low blast radius; main risk is incomplete signal coverage. | Faster triage and clearer promotion/rollback gating evidence. | Inject controlled failure in staging and confirm logs, metrics, and alerts capture it. | 5.0 | 4.1 | 91.9 | intake-ready |
| docs: [automation/gmail-pubsub](https://docs.openclaw.ai/automation/gmail-pubsub) | Automation trigger orchestration | Trigger misconfiguration can create duplicate or noisy executions. | Lower polling overhead and faster event-to-action latency. | Stage one trigger in sandbox, replay sample events, compare latency and errors. | 5.0 | 4.8 | 87.2 | intake-ready |
| docs: [automation/webhook](https://docs.openclaw.ai/automation/webhook) | Automation trigger orchestration | Trigger misconfiguration can create duplicate or noisy executions. | Lower polling overhead and faster event-to-action latency. | Stage one trigger in sandbox, replay sample events, compare latency and errors. | 5.0 | 4.8 | 87.2 | intake-ready |
| docs: [prose](https://docs.openclaw.ai/prose) | Workflow quality and output structure | Higher process complexity can increase runtime cost if over-applied. | Improve output consistency and reduce rerun/edit loops. | A/B test representative tasks for quality score, revision count, and turnaround. | 5.0 | 4.4 | 86.8 | intake-ready |
| docs: [concepts/system-prompt](https://docs.openclaw.ai/concepts/system-prompt) | Workflow quality and output structure | Higher process complexity can increase runtime cost if over-applied. | Improve output consistency and reduce rerun/edit loops. | A/B test representative tasks for quality score, revision count, and turnaround. | 5.0 | 4.0 | 85.2 | intake-ready |
| release: [openclaw 2026.3.13](https://github.com/openclaw/openclaw/releases/tag/v2026.3.13-1) | Core runtime upgrade candidate | Release changes can introduce regressions without staged validation. | Adopt upstream fixes and capabilities with lower long-term drift. | Pin release in staging, run regression suite, compare reliability metrics, confirm rollback. | 5.0 | 4.4 | 82.6 | intake-ready |
| release: [openclaw 2026.3.12](https://github.com/openclaw/openclaw/releases/tag/v2026.3.12) | Core runtime upgrade candidate | Release changes can introduce regressions without staged validation. | Adopt upstream fixes and capabilities with lower long-term drift. | Pin release in staging, run regression suite, compare reliability metrics, confirm rollback. | 5.0 | 4.4 | 82.6 | intake-ready |
