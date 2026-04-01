# Plan: ORION Direct Device Interaction

**Generated**: 2026-03-22
**Estimated Complexity**: High
**Status**: Planning only

## Overview

This plan expands ORION's direct interaction with Cory's devices without breaking the current Gateway model:

- ORION remains the only user-facing ingress.
- Operational execution continues to route through ATLAS, then PULSE/STRATUS/NODE as needed.
- Browser-first automation is the primary direct-action path.
- Typed macOS node actions come before broad UI automation.
- Risky actions stay approval-gated with proof capture.

The goal is not unconstrained desktop autonomy. The goal is a supervised operator stack for repeatable, high-value workflows.

## Scope

In scope:
- managed browser control as ORION's default direct-action lane
- typed macOS node actions for safe local device interaction
- approval policies and proof capture for risky actions
- hooks/cron integration for preparatory device workflows
- a lightweight operator UI for review and approval

Out of scope:
- public or non-loopback control-plane exposure
- unrestricted shell/RCE expansion on chat surfaces
- replacing Task Packets or specialist routing
- broad persistent daemons without explicit approval
- full desktop RPA as the default control model

## Prerequisites

- Current Gateway routing remains intact in [SOUL.md](/Users/corystoner/Desktop/ORION/SOUL.md), [agents/INDEX.md](/Users/corystoner/Desktop/ORION/agents/INDEX.md), and [TOOLS.md](/Users/corystoner/Desktop/ORION/TOOLS.md)
- Security constraints remain binding from [SECURITY.md](/Users/corystoner/Desktop/ORION/SECURITY.md)
- Existing browser, cron, and Mini App references remain the starting point:
  - [README.md](/Users/corystoner/Desktop/ORION/README.md)
  - [openclaw.yaml](/Users/corystoner/Desktop/ORION/openclaw.yaml)
  - [docs/OPENCLAW_CAPABILITY_INTAKE_2026_03_18.md](/Users/corystoner/Desktop/ORION/docs/OPENCLAW_CAPABILITY_INTAKE_2026_03_18.md)

## Dependency Graph

- `T1` depends_on: `[]`
- `T2` depends_on: `[T1]`
- `T3` depends_on: `[T1]`
- `T4` depends_on: `[T2, T3]`
- `T5` depends_on: `[T2, T3]`
- `T6` depends_on: `[T4, T5]`
- `T7` depends_on: `[T4, T5]`
- `T8` depends_on: `[T6, T7]`

Graph:

```text
T1 -> T2 -> T4 -> T6 -> T8
  \-> T3 -> T4 -> T7 -> T8
        \------> T5 -/
T2 ------------> T5 -/
```

## Sprint 1: Control Boundary

**Goal**: Define the safe execution boundary before adding new device powers.

**Demo/Validation**:
- Threat model updates reviewed against current `SECURITY.md`
- Allowed and denied action classes documented
- No new control path bypasses ORION or ATLAS

### T1: Define the direct-interaction policy envelope
- **depends_on**: `[]`
- **Location**: [SECURITY.md](/Users/corystoner/Desktop/ORION/SECURITY.md), [TOOLS.md](/Users/corystoner/Desktop/ORION/TOOLS.md), [src/agents/ORION.md](/Users/corystoner/Desktop/ORION/src/agents/ORION.md), [docs/AGENT_OWNERSHIP_MATRIX.md](/Users/corystoner/Desktop/ORION/docs/AGENT_OWNERSHIP_MATRIX.md)
- **Description**: Add a repo-level policy for device interaction covering allowed surfaces, approval classes, proof requirements, and escalation paths.
- **Complexity**: 5
- **Acceptance Criteria**:
  - Browser control, typed node actions, and UI automation are explicitly distinguished
  - Destructive, identity-bearing, and external-post actions require approval
  - Remote exposure rules remain loopback/tailnet-only unless Cory explicitly opts in
- **Validation**:
  - Manual review against `SECURITY.md`
  - Prompt/routing regression cases for approval-gated actions

### T2: Specify browser-first execution policy
- **depends_on**: `[T1]`
- **Location**: [README.md](/Users/corystoner/Desktop/ORION/README.md), [docs/OPENCLAW_CAPABILITY_INTAKE_2026_03_18.md](/Users/corystoner/Desktop/ORION/docs/OPENCLAW_CAPABILITY_INTAKE_2026_03_18.md), new doc under `docs/`
- **Description**: Standardize when ORION uses the managed OpenClaw browser versus an attached personal browser session.
- **Complexity**: 4
- **Acceptance Criteria**:
  - Managed browser is the default for authenticated automation
  - Personal browser relay is opt-in and explicitly marked as higher trust/risk
  - Proof capture requirements exist for every direct browser workflow
- **Validation**:
  - Scenario table for at least 5 user flows
  - Review against prompt-injection and session-misuse risks

### T3: Specify typed macOS node action model
- **depends_on**: `[T1]`
- **Location**: new doc under `docs/`, [src/agents/ATLAS.md](/Users/corystoner/Desktop/ORION/src/agents/ATLAS.md), [src/agents/STRATUS.md](/Users/corystoner/Desktop/ORION/src/agents/STRATUS.md), [src/agents/PULSE.md](/Users/corystoner/Desktop/ORION/src/agents/PULSE.md)
- **Description**: Define the initial typed local actions ORION can request through ATLAS instead of relying on arbitrary shell execution.
- **Complexity**: 6
- **Acceptance Criteria**:
  - Initial verbs are enumerated with typed inputs/outputs
  - Initial set includes `open_app`, `open_url`, `shortcut`, `finder_reveal`, `notify`, and bounded `applescript`
  - Each verb has approval classification and proof expectations
- **Validation**:
  - Action schema review
  - Abuse-case review for each proposed verb

## Sprint 2: Contract and Routing

**Goal**: Turn policy into concrete repo contracts for specialists and workflows.

**Demo/Validation**:
- Task Packet templates support device actions
- Routing rules clearly separate ORION intake from ATLAS execution
- Operator workflows can be described end-to-end before implementation

### T4: Extend Task Packet and ownership conventions for device control
- **depends_on**: `[T2, T3]`
- **Location**: [docs/TASK_PACKET.md](/Users/corystoner/Desktop/ORION/docs/TASK_PACKET.md), [docs/ATLAS_ORCHESTRATION.md](/Users/corystoner/Desktop/ORION/docs/ATLAS_ORCHESTRATION.md), [docs/AGENT_OWNERSHIP_MATRIX.md](/Users/corystoner/Desktop/ORION/docs/AGENT_OWNERSHIP_MATRIX.md)
- **Description**: Add packet fields for device target, action class, approval requirement, proof bundle, and rollback notes.
- **Complexity**: 5
- **Acceptance Criteria**:
  - Device workflows have a standard packet shape
  - Ownership is explicit across ORION, ATLAS, PULSE, STRATUS, POLARIS
  - Proof and rollback notes are mandatory for write-capable actions
- **Validation**:
  - Packet examples for browser task, macOS task, and scheduled prep task
  - Task packet lint/update tests if current guardrails support them

### T5: Define approval and proof-capture contracts
- **depends_on**: `[T2, T3]`
- **Location**: new doc under `docs/`, [config/orion_policy_rules.json](/Users/corystoner/Desktop/ORION/config/orion_policy_rules.json), prompt safety fixtures under `config/promptfoo/`
- **Description**: Define the approval ladder and proof bundle required for risky local actions.
- **Complexity**: 6
- **Acceptance Criteria**:
  - Approval classes cover read-only, local-write, identity-bearing, destructive, and persistent changes
  - Proof bundle format includes action intent, artifact paths, screenshots/output, and final status
  - ORION response rules distinguish `pending approval`, `in progress`, and `verified`
- **Validation**:
  - Prompt regression tests for approval language
  - Sample proof bundle reviewed for completeness

## Sprint 3: Operator Packs

**Goal**: Package the highest-value direct-action workflows before building more surface area.

**Demo/Validation**:
- At least 3 workflows are fully specified
- Each workflow uses browser-first or typed-node-first decisions explicitly
- Each workflow has stop gates and verification steps

### T6: Design browser-led operator packs
- **depends_on**: `[T4, T5]`
- **Location**: new docs under `docs/operator-packs/`, [src/agents/POLARIS.md](/Users/corystoner/Desktop/ORION/src/agents/POLARIS.md), [src/agents/WIRE.md](/Users/corystoner/Desktop/ORION/src/agents/WIRE.md)
- **Description**: Specify high-value browser-led workflows such as inbox triage, meeting prep, and portal submission staging.
- **Complexity**: 7
- **Acceptance Criteria**:
  - At least 3 workflows with inputs, outputs, specialist handoffs, and approval points
  - WIRE and POLARIS roles are explicit where retrieval/admin prep is needed
  - Each workflow defines what is automated versus what is only staged for approval
- **Validation**:
  - Dry-run walkthroughs for each workflow
  - Coverage review for common failure modes

### T7: Design local-device operator packs
- **depends_on**: `[T4, T5]`
- **Location**: new docs under `docs/operator-packs/`, [src/agents/ATLAS.md](/Users/corystoner/Desktop/ORION/src/agents/ATLAS.md), [src/agents/STRATUS.md](/Users/corystoner/Desktop/ORION/src/agents/STRATUS.md)
- **Description**: Specify local-device workflows such as app launching, note creation, file reveal/attachment prep, and notification-driven prep.
- **Complexity**: 7
- **Acceptance Criteria**:
  - At least 3 local-device workflows are typed and bounded
  - No workflow requires unrestricted shell as the primary mechanism
  - Each workflow includes rollback and user-visible confirmation behavior
- **Validation**:
  - Action-by-action review for host safety
  - Verification checklist for each workflow

## Sprint 4: Automation and Operator UI

**Goal**: Add supervised automation and a review surface after the workflow contracts are stable.

**Demo/Validation**:
- Scheduled prep flows are clearly separated from direct execution
- Approval queue and proof review concepts are defined
- Mini App remains optional and non-critical-path

### T8: Define supervised automation and Mission Control
- **depends_on**: `[T6, T7]`
- **Location**: [app/](/Users/corystoner/Desktop/ORION/app), [src/plugins/telegram/miniapp/](/Users/corystoner/Desktop/ORION/src/plugins/telegram/miniapp), [docs/TELEGRAM_AGENT_CHAT_RULES.md](/Users/corystoner/Desktop/ORION/docs/TELEGRAM_AGENT_CHAT_RULES.md), [docs/PERSONAL_OPS_AUTOMATIONS.md](/Users/corystoner/Desktop/ORION/docs/PERSONAL_OPS_AUTOMATIONS.md)
- **Description**: Define how cron/hooks prepare work, queue approvals, and surface proof bundles through an optional operator view.
- **Complexity**: 8
- **Acceptance Criteria**:
  - Cron/hooks only prepare or queue work unless explicit approval exists
  - Approval queue design does not require exposing new public control paths
  - Mini App integration is optional and respects `OPENCLAW_ROUTE_COMMANDS=1` security rules
- **Validation**:
  - Architecture review against `SECURITY.md`
  - Sample end-to-end flow from scheduled prep to approved execution to proof review

## Missing Workstreams

- **Action schema registry**: central typed definitions for browser and node verbs, approval class, and proof expectations
- **Regression harness**: prompt/routing tests for approval handling, unsafe asks, and status wording
- **Artifact storage model**: where screenshots, proof bundles, and workflow traces live on disk
- **Failure handling**: retry, cancellation, stale approval expiry, and partial-completion behavior
- **Human factors**: concise user-facing language for what ORION will do, what it already did, and what still needs approval

## Testing Strategy

- Add prompt safety/regression coverage for:
  - approval-required local actions
  - destructive and persistent change requests
  - scheduled prep flows that must not imply completion
- Add Task Packet validation coverage if packet schema changes
- Add workflow dry-run checklists for every operator pack
- Add policy review checklist against:
  - [SECURITY.md](/Users/corystoner/Desktop/ORION/SECURITY.md)
  - [TOOLS.md](/Users/corystoner/Desktop/ORION/TOOLS.md)
  - [SOUL.md](/Users/corystoner/Desktop/ORION/SOUL.md)

## Top Risks

- Expanding device control faster than approval and proof infrastructure
- Accidentally creating a second operator plane that bypasses ORION or ATLAS
- Letting personal browser/session control become the default instead of the exception
- Using arbitrary shell or broad AppleScript where typed actions would suffice
- Treating the Mini App as a trusted control surface without explicit risk acceptance

## Rollback Plan

- Keep rollout doc-first and contract-first until approval and proof rules are merged
- Gate any future implementation behind the policy envelope from `T1`
- If a future implementation proves too risky, disable the specific operator pack without removing the broader routing model
- Preserve loopback-only assumptions and do not enable remote control or command-routing exposure by default

## Recommended First Implementation Slice

If execution starts after planning, the best first slice is:

1. `T1` direct-interaction policy envelope
2. `T3` typed macOS node action model
3. `T4` Task Packet extensions
4. `T5` approval and proof-capture contract

That sequence yields a safe contract layer before any new device-control implementation work.
