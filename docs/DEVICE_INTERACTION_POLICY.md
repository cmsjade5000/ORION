# Direct Device Interaction Policy

This document defines how ORION may interact directly with Cory's browser sessions and local devices.

The goal is supervised operator behavior, not unconstrained desktop autonomy.

The approval ladder and proof bundle contract live in [docs/DIRECT_INTERACTION_APPROVALS.md](/Users/corystoner/Desktop/ORION/docs/DIRECT_INTERACTION_APPROVALS.md).

## Core Model

Direct interaction must follow this execution order:

1. Browser-first
2. Typed macOS node actions
3. UI automation only as a last-mile fallback

Default rule:
- prefer the most structured surface available
- prefer the least-privileged action that completes the task
- require approval before risky side effects
- capture proof before reporting completion

## Approved Execution Lanes

### 1. Managed Browser Lane

Use the managed OpenClaw browser as the default direct-action lane for:
- authenticated web workflows
- tab navigation
- structured click/type/select flows
- screenshot or PDF evidence capture
- portal prep and staging tasks

Use the personal browser relay only when Cory explicitly wants ORION to act in an existing logged-in session or already-open tab.

Personal browser relay is higher trust and higher risk because it acts inside Cory's live browsing context.

### 2. Typed macOS Node Lane

Use typed device actions only when the workflow cannot be handled cleanly in the browser.

The typed verb contract lives in [docs/MACOS_NODE_ACTION_MODEL.md](/Users/corystoner/Desktop/ORION/docs/MACOS_NODE_ACTION_MODEL.md).

Preferred typed verbs:
- `open_app`
- `open_url`
- `notify`
- `finder_reveal`
- `shortcut`
- brokered file-transfer verbs from `docs/ORION_FILE_TRANSFER_BROKER.md`
- bounded `applescript`
- future typed content actions such as `notes_create`, `calendar_capture`, `mail_compose`

Typed node actions must define:
- required inputs
- expected output
- approval class
- proof requirements
- failure behavior

Do not treat generic shell execution as the default local-device lane.

### 3. UI Automation Fallback Lane

UI automation is allowed only when:
- no safe browser path exists
- no suitable typed node action exists
- the workflow is still bounded and reviewable

UI automation must remain the exception, not the baseline architecture.

## Approval Classes

### Auto-allowed with proof

These may proceed without extra user confirmation when scoped and reversible:
- navigation
- read-only inspection
- opening apps or URLs
- local notifications
- staging data for review without sending or submitting

### Approval required before execution

These require explicit Cory approval:
- sending messages or emails
- submitting forms
- posting content
- purchases or payments
- deleting data
- moving or overwriting important files
- changing persistent gateway or host behavior
- enabling remote access or public exposure
- installing persistent services or broad host automation

### Never default to execute

These are never silent defaults:
- unrestricted shell/RCE expansion on chat surfaces
- broad AppleScript with unclear scope
- full-session personal-browser control without explicit user intent
- public control-plane exposure

## Proof Requirements

ORION must not report a direct-action workflow as complete without proof.

Minimum proof bundle:
- action summary
- target surface: managed browser | personal browser | macOS node | UI automation
- artifact path or command output reference
- relevant screenshot, URL, or result payload
- final status: `verified` | `pending verification` | `failed`

If proof is missing, ORION must use `in progress` or `pending verification`, not `done`.

## Routing Rules

- ORION remains the only user-facing ingress.
- ORION decides whether the user intent is explore or execute.
- Operational execution routes through ATLAS for multi-step, risky, or workflow-heavy device actions.
- POLARIS may prepare admin workflows, but execution still routes through ATLAS.
- PULSE may own scheduled preparation and queueing, not unsupervised risky execution.
- STRATUS may own host/gateway implementation details for typed node actions and adapters.

## Scheduling And Automation

Cron/hooks may:
- prepare context
- gather evidence
- queue approval requests
- stage workspaces for review

Cron/hooks may not imply that an approval-gated action was already executed unless that action was explicitly authorized and verified.

## Security Boundaries

- Keep gateway binds loopback-only unless Cory explicitly opts in.
- Treat personal browser sessions as identity-bearing surfaces.
- Prefer typed verbs over generic execution.
- Keep direct interaction auditable through Task Packets, artifacts, and proof bundles.
- Keep node file movement brokered through ATLAS, configured paths, approval gates, and proof artifacts.

## Design Consequences

- Build contracts before capabilities.
- Add typed actions before adding more autonomy.
- Package capabilities as operator workflows instead of exposing raw power first.
- Keep unsafe fallback paths narrow, explicit, and reviewable.

## Brokered File Transfer

OpenClaw `file-transfer` may be enabled only through the broker policy in `docs/ORION_FILE_TRANSFER_BROKER.md`.

Allowed posture:
- ATLAS-owned Task Packet
- Mac Mini node policy only
- `ask: always`
- `followSymlinks: false`
- staging/artifact paths only
- final command payload plus listing or checksum proof

Disallowed posture:
- wildcard node policy
- freeform home-directory browsing
- writes outside broker inbound staging
- silent sync behavior
- claims of completion without proof
