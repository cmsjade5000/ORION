# OpenClaw Capability Intake

Date: 2026-03-18
Status: decision-ready intake brief
Scope: research and evaluation only; no installs, config changes, or channel changes

## Dependency Graph

- `T1` depends_on: `[]`
- `T2` depends_on: `[]`
- `T7` depends_on: `[]`
- `T3` depends_on: `[T1]`
- `T4` depends_on: `[T2]`
- `T5` depends_on: `[T3, T4, T7]`
- `T6` depends_on: `[T5]`

## Summary

ORION already has strong local coverage for Task Packets, cron, messaging, hooks, memory, browser access, safety gates, and a broad workspace skill tree. The highest-value intake items are therefore the ones that add net-new leverage rather than duplicating the current repo posture:

- official OpenClaw discovery and orchestration surfaces not yet fully exploited locally
- durable evaluation and observability infrastructure
- structured external retrieval and richer GitHub automation
- formal runbook execution patterns worth piloting before adoption

## Method

- Prioritized official OpenClaw docs and repositories over community summaries
- Used community candidates only when they were clearly maintained, officially listed, or materially different from local capability
- Screened every candidate against ORION's single-bot, internal-specialist, and secret-hygiene rules
- Rejected novelty channels and duplicative tool layers by default

## T1: Official Source Index

| Name | URL | Capability | ORION relevance | Local overlap |
|---|---|---|---|---|
| OpenClaw core repo | https://github.com/openclaw/openclaw | Upstream source of truth for runtime behavior, agents, tools, and release lineage | Baseline for any future compatibility or extension work | Covered |
| OpenClaw releases | https://github.com/openclaw/openclaw/releases | Version-specific change tracking | Needed to tie ORION behavior and docs to exact upstream versions | Partial |
| OpenClaw docs home | https://docs.openclaw.ai/ | Canonical docs entry point | Baseline documentation index for operators and future research | Covered |
| Plugin architecture | https://docs.openclaw.ai/plugin | Plugin model, manifests, context engines, CLI/tool registration | Relevant for any net-new extension surface | Partial |
| ClawHub docs | https://docs.openclaw.ai/tools/clawhub | Skill registry and install/discovery model | Best official path for discovering versioned skills | Partial |
| ClawHub repo | https://github.com/openclaw/clawhub | Backing repository for the official skill registry | Useful for evaluating moderation and packaging patterns | Partial |
| Prose docs | https://docs.openclaw.ai/prose | Markdown-defined multi-agent workflows | Useful for repeatable, approval-safe flows beyond ad hoc tasks | Partial |
| ACP agents docs | https://docs.openclaw.ai/tools/acp-agents | External harness sessions via ACP | Biggest official gap relative to current native-subagent posture | Partial |
| Browser docs | https://docs.openclaw.ai/tools/browser | Managed browser automation and routing | Useful, but partially overlapped by current local browser skills | Partial |
| Cron docs | https://docs.openclaw.ai/cron/ | Scheduled jobs and isolated session modes | Important for keeping ORION automation aligned with upstream cron semantics | Covered |
| Message CLI docs | https://docs.openclaw.ai/cli/message | Messaging actions across channels | Already aligned with ORION's chat-native operating model | Covered |
| Hooks docs | https://docs.openclaw.ai/automation/hooks | Internal hook model and bundled hooks | Already reflected in ORION's `session-memory` and `command-logger` posture | Covered |
| Memory docs | https://docs.openclaw.ai/concepts/memory | Memory persistence and compaction semantics | Needed to reason about ORION memory behavior and plugin expectations | Covered |
| Community plugin index | https://docs.openclaw.ai/plugins/community | Officially listed community plugins | Best quality bar for external plugin discovery | Partial |
| nix-openclaw | https://github.com/openclaw/nix-openclaw | Reproducible packaging and plugin distribution patterns | Useful if ORION later needs standardized multi-machine or reproducible installs | Partial |

## T3: Local ORION Capability Map

| Capability area | Status | Local evidence | Intake implication |
|---|---|---|---|
| Single ingress and specialist routing | Covered | `README.md`, `AGENTS.md`, `agents/INDEX.md`, `docs/ORION_SINGLE_BOT_ORCHESTRATION.md` | New tools must preserve ORION as sole user-facing ingress |
| Task Packet discipline | Covered | `docs/TASK_PACKET.md`, `tasks/INBOX/`, `skills/task-packet-guard/SKILL.md` | External orchestration layers must complement, not replace, Task Packets |
| Cron and recurring automation | Covered | `skills/cron-manager/SKILL.md`, `docs/PERSONAL_OPS_AUTOMATIONS.md`, `docs/FOLLOW_THROUGH.md` | Avoid duplicative scheduler-first tools unless they add clear orchestration value |
| Messaging and channel ops | Covered | `openclaw.yaml`, `openclaw.json.example`, `docs/DISCORD_SETUP.md`, `docs/TELEGRAM_AGENT_CHAT_RULES.md`, `skills/slack-handbook/SKILL.md`, `skills/agentmail/SKILL.md` | New channels raise policy and attack-surface questions |
| Browser and web workflows | Covered | `skills/mino-web-agent/SKILL.md`, `skills/peekaboo/SKILL.md`, `README.md`, `docs/PDF_REVIEW_WORKFLOW.md` | Browser additions should be structured and grounded, not generic RPA |
| Hooks and bootstrap | Covered | `openclaw.yaml`, `openclaw.json.example`, `docs/OPENCLAW_CONFIG_MIGRATION.md` | Plugin or hook changes must align with existing internal hooks |
| Memory and compaction | Covered | `openclaw.yaml`, `openclaw.json.example`, `docs/MEMORY_BACKENDS.md`, `docs/OPENCLAW_2026_3_13_UPGRADE_NOTES.md` | Memory vendors are optional, not urgent |
| Security and preflight gates | Covered | `SECURITY.md`, `KEEP.md`, `TOOLS.md`, `skills/secure-code-preflight/SKILL.md`, `skills/supply-chain-verify-scan/SKILL.md`, `skills/llm-redteam-gate/SKILL.md`, `skills/llm-vuln-probe/SKILL.md` | New tools should improve gates, not bypass them |
| GitHub and repo operations | Partial | `skills/github/SKILL.md`, `skills/pr-manager/SKILL.md`, `skills/ci-failure-triage/SKILL.md` | Richer MCP-based GitHub access could add net-new value |
| Observability and trace evals | Partial | `skills/langfuse-trace-eval-bootstrap/SKILL.md`, `eval/`, `docs/ORION_ERROR_REVIEW.md` | Strong opportunity for a more durable platform |
| Structured external retrieval | Partial | Browser skills, WIRE role, `skills/discovery-scorecard/SKILL.md`, `skills/evidence-core/SKILL.md` | Firecrawl-class crawl grounding is a meaningful gap |
| Formal runbook execution | Partial | Existing runbooks in `docs/`, `skills/gateway-service/SKILL.md`, `skills/system-metrics/SKILL.md` | Runbook MCP is worth evaluation, not adoption by default |
| Skill discovery and packaging | Partial | Large local `skills/` tree, manual repo-local skills | Official ClawHub workflow is worth evaluating |
| ACP external harness sessions | Missing | No current repo-native ACP integration docs or wrappers | Highest-value official capability gap |
| New messaging channels beyond Telegram/Discord/Slack/email | Not worth adding now | Current repo is Telegram-first and Discord-optional | Additional channels are a policy burden unless there is a clear user need |

## T7: Policy and Security Gate

| Gate question | Result | Notes |
|---|---|---|
| Preserve ORION as sole user-facing ingress? | Required | Reject tools that message Cory directly outside ORION or bypass specialist routing |
| Avoid secret sprawl outside repo policy? | Required | Favor SecretRef or local secret files; reject tools that normalize plaintext secret sprawl |
| Avoid destructive or auto-install behavior during evaluation? | Required | All pilot work starts read-only |
| Improve evidence, control, reliability, or operator leverage more than novelty? | Required | Novelty channels and duplicate browser stacks fail this gate |
| Compatible with Task Packet discipline? | Preferred | Strong positive signal if the tool can coexist with current delegation patterns |
| Compatible with internal-only specialist posture? | Required | Specialist-only tools are fine; specialist-to-user messaging is not |

Gate outcomes:

- `allow`: `ClawHub` audit path, `promptfoo`, `langfuse`, `github-mcp-server`, `firecrawl`
- `allow with mitigation`: `garak`, `playwright-mcp`, `runbook-mcp-server`, `openclaw-runbook`, `openclaw-wechat`
- `reject for now`: `local-skills-mcp`, `awesome-openclaw-skills` as an adoption target, extra messaging channels without user need, full local model-serving stacks, pixel-only desktop RPA stacks

## T2 + T4 + T5: Screened Candidate Shortlist

### Adopt Soon

| Name | URL | Source type | Official status | Category | Why ORION benefits | Local overlap | Maintenance signal | Risk | Integration effort | Policy gate | Next step |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ClawHub plus ACP/Prose audit path | https://docs.openclaw.ai/tools/clawhub | Official docs and registry | Official | Skill discovery and orchestration | Adds the most relevant official capabilities ORION is not fully using yet: skill discovery, ACP sessions, and workflow formalization | Partial overlap with local skills and `open-prose` enablement | Official OpenClaw docs and repos; current as of March 2026 research pass | Low | Low | Allow | Audit the official docs path first before adopting any third-party skill packs |
| promptfoo | https://github.com/promptfoo/promptfoo | Adjacent repo | Third-party, high credibility | Evals and regression testing | Best fit for repeatable prompt, routing, tool, and safety regressions in CI | Overlaps some local security/eval skills but is much more mature as a framework | Strong public maintenance and release cadence | Low | Medium | Allow | Run a read-only evaluation of fit against existing `eval/` flows |
| langfuse | https://github.com/langfuse/langfuse | Adjacent repo | Third-party, high credibility | Observability and trace evals | Fills the clearest platform gap around durable traces, datasets, prompts, and evaluation history across handoffs | Partial overlap with `langfuse-trace-eval-bootstrap` and local eval docs | Very strong public maintenance and release cadence | Medium | Medium | Allow | Compare against current trace bootstrap skill and define a minimal integration envelope |
| github-mcp-server | https://github.com/github/github-mcp-server | Adjacent repo | Official GitHub | GitHub MCP surface | Extends current `gh`-based GitHub skill into a richer structured tool surface for repo, PR, issues, actions, and code-security workflows | Medium overlap with local GitHub skills | Strong public maintenance and release cadence | Low-Medium | Medium | Allow | Evaluate whether MCP adds enough over current `gh` workflows to justify setup cost |
| firecrawl | https://github.com/firecrawl/firecrawl | Adjacent repo | Third-party, high credibility | Structured web retrieval | Fills a real gap around crawl-grounded, extract-first retrieval beyond browser and manual WIRE workflows | Medium overlap with browser and evidence skills | Strong public maintenance and release cadence | Low-Medium | Medium | Allow | Evaluate for research and document-grounding use cases only |

### Research Deeper

| Name | URL | Source type | Official status | Category | Why ORION benefits | Local overlap | Maintenance signal | Risk | Integration effort | Policy gate | Next step |
|---|---|---|---|---|---|---|---|---|---|---|---|
| garak | https://github.com/NVIDIA/garak | Adjacent repo | Third-party, high credibility | LLM security scanning | Useful as a second-layer adversarial scanner on top of local red-team gates | Medium overlap with existing red-team/security skills | Strong public maintenance | Low-Medium | Medium | Allow with mitigation | Compare its coverage against existing local red-team workflows before adopting |
| playwright-mcp | https://github.com/microsoft/playwright-mcp | Adjacent repo | Official Microsoft | Browser MCP surface | Strong structured browser control, but ORION already has meaningful local browser capability | Medium-High overlap with current browser skills | Strong public maintenance | Low-Medium | Medium | Allow with mitigation | Evaluate only if current browser flows prove too brittle or too manual |
| runbook-mcp-server | https://github.com/runbookai/runbook-mcp-server | Community repo | Third-party, moderate credibility | Formal runbook execution | Could turn ORION's runbook culture into a structured execution layer | Medium overlap with local docs and Task Packets | Moderate public signal | Medium | Medium | Allow with mitigation | Read-only pilot to determine whether it adds more than current docs plus Task Packets |
| openclaw-runbook | https://github.com/digitalknk/openclaw-runbook | Community repo | Third-party, moderate credibility | OpenClaw operational playbooks | Useful as an external runbook pattern library | Medium overlap with local docs | Lighter public signal | Medium | Low | Allow with mitigation | Mine for patterns, not adoption |
| openclaw-wechat | https://github.com/icesword0760/openclaw-wechat | Community plugin | Officially listed community plugin | Messaging channel expansion | Interesting as a community-plugin reference, not as an immediate ORION channel target | High overlap with current messaging surfaces | Officially listed, but small repo footprint | High | Medium | Allow with mitigation | Treat as a plugin-shape reference unless channel strategy changes |

### Ignore For Now

| Name | URL | Type | Why not now |
|---|---|---|---|
| local-skills-mcp | https://github.com/kdpa-llc/local-skills-mcp | Community MCP server | Too duplicative of ORION's repo-local skill tree and skill infrastructure for current needs |
| awesome-openclaw-skills | https://github.com/sundial-org/awesome-openclaw-skills | Discovery catalog | Useful for idea mining, but too noisy to treat as an adoption target over official ClawHub |
| n8n | https://github.com/n8n-io/n8n | Workflow automation platform | Powerful, but too broad and operationally heavy for this intake pass |
| Extra messaging channels without a user need | N/A | Capability category | Violates the repo's default bias against expanding the attack surface for novelty |
| Full local model-serving stacks | N/A | Capability category | Out of scope for this pass and not aligned with the stated objective |
| Pixel-only desktop RPA stacks | N/A | Capability category | Duplicative when ORION already has browser tools and safer structured automation options |

## T6: Pilot Specs

### Pilot 1: Official Capability Audit

Target:
- `ClawHub`
- `ACP agents`
- `Prose`
- plugin docs and community plugin index

Read-only evaluation step:
- Review official docs and repos only

Success criteria:
- Determine whether ACP sessions solve a real ORION gap not covered by native subagents
- Determine whether ClawHub adds a better skill discovery and versioning path than the current manual repo-local model
- Determine whether Prose should become the default format for repeatable research and triage flows

Validation questions:
- Which of these surfaces are already partially enabled in ORION but underused?
- What exact local docs or scripts would need to change later if ORION adopted them?
- Does any official surface conflict with ORION's Task Packet discipline or single-bot policy?

Security constraints:
- No installs
- No plugin enablement
- No channel changes

Stop gates:
- Any recommendation that requires enabling a new external delivery surface
- Any proposal that changes specialist-to-user routing

Rollback path:
- None needed for this pilot because it is read-only

### Pilot 2: Runbook Execution Candidate

Target:
- `runbook-mcp-server`

Fallback comparison source:
- `openclaw-runbook`

Read-only evaluation step:
- Inspect README, examples, configuration model, and execution assumptions

Success criteria:
- Determine whether formal runbook execution adds enough value over current runbooks plus Task Packets
- Identify whether the MCP model can stay internal-only and policy-compliant
- Produce a yes/no recommendation with explicit overlap notes

Validation questions:
- Does it encode execution state, approvals, and evidence in a way that improves on current docs?
- Can it operate without bypassing ORION or creating a parallel operator plane?
- Does it increase maintenance burden more than it reduces ambiguity?

Security constraints:
- No server install
- No credential creation
- No MCP registration

Stop gates:
- Any design that encourages specialists to act outside ORION mediation
- Any setup that normalizes plaintext secrets or remote uncontrolled execution

Rollback path:
- None needed for this pilot because it is read-only

### Pilot 3: Evaluation Harness Candidate

Target:
- `promptfoo`

Comparison set:
- local `eval/`
- `skills/llm-redteam-gate/SKILL.md`
- `skills/llm-vuln-probe/SKILL.md`

Read-only evaluation step:
- Review docs, config shape, test model, and CI fit

Success criteria:
- Determine whether `promptfoo` should become ORION's primary regression harness for prompts, routing, and tool behavior
- Identify a minimum viable evaluation envelope that coexists with current repo eval assets
- Specify what a future no-risk pilot would validate first

Validation questions:
- Can ORION use it without replacing existing local evaluation scripts immediately?
- Does it improve change detection for Task Packet prompts, safety boundaries, and routing logic?
- Is the maintenance overhead acceptable relative to current eval gaps?

Security constraints:
- No package install
- No CI mutation
- No external data upload

Stop gates:
- Any setup requiring immediate provider or secret sprawl
- Any plan that bypasses current local safety gates rather than integrating with them

Rollback path:
- None needed for this pilot because it is read-only

## Recommended Next Actions

1. Execute Pilot 1 first because it is official, low-risk, and likely to clarify the rest of the shortlist.
2. Execute Pilot 3 second because evaluation leverage is more valuable to ORION right now than a new runbook layer.
3. Execute Pilot 2 third only if Pilot 1 does not reveal an official OpenClaw-native runbook path that supersedes it.

## Notes

- Current official/community signals were refreshed during this intake on 2026-03-18.
- This brief intentionally favors evidence and operator leverage over novelty.
- Adoption is not approved by this document; only evaluation is recommended.
