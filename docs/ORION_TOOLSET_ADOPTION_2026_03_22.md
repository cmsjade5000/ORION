# ORION Toolset Adoption 2026-03-22

Historical note:
- This document is a March 2026 recommendation snapshot.
- For the current baseline and current pilot posture, use:
  - `docs/ORION_RUNTIME_BASELINE_2026_04_07.md`
  - `docs/ORION_TOOL_PILOTS_2026_04.md`
  - `docs/ORION_AGENT_SYSTEM_SWEEP_2026_04_07.md`

Status: implementation-ready adoption memo  
Scope: additive toolset expansion without changing ORION's single-ingress policy

## Dependency Graph

- `T1` depends_on: `[]`
- `T2` depends_on: `[T1]`
- `T3` depends_on: `[T1]`
- `T4` depends_on: `[T1]`
- `T5` depends_on: `[T1]`
- `T6` depends_on: `[T2, T3]`
- `T7` depends_on: `[T2, T4]`
- `T8` depends_on: `[T2, T5]`
- `T9` depends_on: `[T6, T7, T8]`
- `T10` depends_on: `[T9]`

## Summary

ORION already has a broad local capability surface. The implementation work here is not "add more random tools." It is:

1. close documented-vs-runtime gaps
2. standardize official OpenAI and OpenClaw-native leverage
3. promote observability and structured retrieval to first-class layers
4. add third-party complements only where they materially outperform the current repo-local stack

## T1 Runtime Parity Audit

depends_on: []

Verified locally on 2026-03-22:

- `openclaw --version` -> `OpenClaw 2026.3.13 (61d171a)`
- `codex --version` -> `codex-cli 0.115.0`
- `openclaw config validate --json` -> `{"valid":true,...}`
- `openclaw config get tools` confirms `tools.profile = "coding"`
- `openclaw config get plugins` confirms the current plugin allowlist is `telegram`, `discord`, `slack`, `mochat`, `memory-lancedb`, `open-prose`
- `codex mcp list` currently reports no MCP servers configured

Gap table:

| Tool | Documented | Available | Blocked | Action needed |
| --- | --- | --- | --- | --- |
| `apply_patch` | README still warns it may be unavailable in the current runtime allowlist | Codex CLI exposes `apply`, but OpenClaw agent-tool availability is not directly enumerable from the CLI | Reported in repo docs | Add a live ORION smoke test that requires patch application and record the result |
| `memory_search` | README still warns it may be unavailable | OpenClaw `memory` CLI exists and `memory-lancedb` is enabled | Reported in repo docs | Add a live ORION memory-search smoke test and split CLI evidence from agent-tool evidence |
| `memory_get` | README still warns it may be unavailable | OpenClaw `memory` CLI exists and `memory-lancedb` is enabled | Reported in repo docs | Add a live ORION memory-read smoke test and record the result |
| `cron` | README still warns it may be unavailable | OpenClaw `cron` CLI exists, so gateway scheduler support is installed | Reported in repo docs | Split "gateway cron support" from "agent-level cron tool support" in docs and add a live tool smoke test |

Decision:

- Treat `apply_patch`, `memory_search`, `memory_get`, and agent-level `cron` as `pending verification` until a live ORION turn proves them.
- Do not claim repo/runtime parity until the smoke checks exist and pass.

## T2 Official Docs And Worker Surfaces

depends_on: [T1]

Decision: `Docs MCP + Codex MCP`

Why:

- Official OpenAI guidance now favors Docs MCP for OpenAI-related work.
- Codex already exposes `mcp-server` and `app-server` surfaces in the installed local CLI.
- Codex MCP is a better first worker-surface step than Codex SDK because it is additive and closer to ORION's existing tool/delegation model.

Implementation choice:

- Standardize OpenAI Docs MCP usage in [AGENTS.md](/Users/corystoner/Desktop/ORION/AGENTS.md).
- Pilot Codex MCP before Codex SDK.
- Defer Codex SDK until the MCP pilot proves there is a real need for resumable structured worker sessions beyond current ORION patterns.

## T3 OpenClaw-Native Expansion

depends_on: [T1]

Decisions:

- `ClawHub`: pilot next
- `ACP`: pilot next
- `OpenProse defaulting`: partial yes

Interpretation:

- ClawHub should become the preferred skill discovery and refresh path once the runtime parity issue is closed.
- ACP is the largest official capability gap, but it should be piloted only after the repo stops overstating current runtime parity.
- OpenProse is already enabled and should become the default format for repeatable internal research, triage, and review workflows, not for every task.

## T4 Observability And Evaluation Stack

depends_on: [T1]

Decision: `Promptfoo primary for prompt/routing/tool regressions; Langfuse primary for traces; keep Opik as a comparison candidate`

Why:

- Promptfoo is already in the repo and is the lowest-friction immediate expansion.
- Langfuse already has bootstrap artifacts and partial code references in-tree.
- Opik is credible, but there is no reason to replace the in-tree Langfuse posture before Langfuse has been made first-class.

Implementation choice:

- Expand Promptfoo from safety-only into Task Packet, routing, evidence-handling, and tool-contract coverage.
- Keep `@opik/opik-openclaw` in the pilot queue, not the adopt-first queue.

## T5 Retrieval And Repo Operations

depends_on: [T1]

Decisions:

- `github-mcp-server`: pilot next
- `firecrawl`: pilot next

Why:

- Current GitHub handling is skill- and shell-driven; GitHub MCP is the cleanest structured upgrade.
- Current external retrieval is browser-heavy; Firecrawl is the clearest extraction-first complement.

## T6 Codex Product-Surface Options

depends_on: [T2, T3]

Decision: `no app-server by default`

Reason:

- The local CLI exposes `app-server`, but there is no proof yet that ORION needs another product surface before Codex MCP is piloted.
- If an app-server is justified later, compare first-party Codex app-server against `openclaw-codex-app-server` after the worker-surface pilot.

## T7 Context Fidelity Layer

depends_on: [T2, T4]

Decision: `no-go for now on lossless-claw`

Reason:

- It is a context-engine plugin with real trust-boundary cost.
- ORION should only adopt it if compaction drift is shown to be a real operational problem after the trace stack is improved.

## T8 Voice And Escalation Surfaces

depends_on: [T2, T5]

Decision: `defer`

Reason:

- `@openclaw/voice-call` is credible, but there is no concrete requirement yet.
- Extra channel plugins remain out of scope unless tied to a specific user need.

Explicit defers:

- `@openclaw/voice-call`
- WeCom / QQ / DingTalk-style channel additions

## T9 Consolidated Shortlist

depends_on: [T6, T7, T8]

### Adopt First

- runtime parity fixes and smoke tests
- OpenAI Docs MCP discipline
- broader Promptfoo coverage

### Pilot Next

- ClawHub
- ACP
- `github-mcp-server`
- `firecrawl`
- Langfuse as the default trace plane

### Keep Researching

- Codex MCP
- Codex SDK
- `@opik/opik-openclaw`
- `openclaw-codex-app-server`
- `lossless-claw`
- `@openclaw/voice-call`

### Reject For Now

- extra chat channels without a concrete user need
- duplicative browser/RPA stacks
- broad workflow platforms that bypass Task Packet discipline

## T10 Rollout Design

depends_on: [T9]

### Phase 1: Close Runtime Truth Gap

- add refreshable runtime audit script
- add live smoke-test placeholders for `apply_patch`, `memory_search`, `memory_get`, and `cron`
- update docs so they distinguish CLI/runtime support from agent-tool support

Success metrics:

- no repo doc claims a tool is available without evidence
- runtime audit is reproducible from one command

### Phase 2: Standardize Official Leverage

- enforce OpenAI Docs MCP guidance
- expand Promptfoo coverage
- pilot ClawHub and ACP discovery/evaluation paths

Success metrics:

- OpenAI-related work uses official doc retrieval by default
- Promptfoo covers routing, Task Packet, and tool-contract regressions

### Phase 3: Add Structured Operator Leverage

- pilot GitHub MCP
- pilot Firecrawl
- promote Langfuse to the default trace plane

Success metrics:

- GitHub tasks gain structured repo/PR/action access
- evidence-heavy research has a crawl-grounded path
- runtime traces are durable and reviewable

### Phase 4: Conditional Expansion

- pilot Codex MCP
- revisit Codex SDK
- revisit app-server choice
- revisit lossless-claw and voice-call only if justified by measured pain

Success metrics:

- new worker surfaces prove value without creating a second ingress
- no new plugin/tool weakens ORION's routing or trust-boundary posture

## Verification Commands

```bash
python3 scripts/orion_toolset_audit.py --output-json tmp/orion_toolset_audit_latest.json --output-md tmp/orion_toolset_audit_latest.md
openclaw config validate --json
openclaw config get tools
openclaw config get plugins
openclaw agents bindings --json
codex --version
codex mcp list
make redteam-validate
```

## Notes

- This memo keeps third-party tools in scope, but not ahead of official/native surfaces.
- The first concrete repo change was standardizing official OpenAI Docs retrieval guidance in [AGENTS.md](/Users/corystoner/Desktop/ORION/AGENTS.md).
- The next operational step after this memo is implementing live smoke tests for the four parity-gap tools.
