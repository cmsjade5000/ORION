# macOS Node Action Model

This document defines the first typed local-device actions ORION may request through ATLAS.

It exists to keep local device interaction structured, reviewable, and safer than generic shell-driven automation.

## Purpose

Typed node actions are the second execution lane in [docs/DEVICE_INTERACTION_POLICY.md](/Users/corystoner/Desktop/ORION/docs/DEVICE_INTERACTION_POLICY.md):

1. managed browser first
2. typed macOS node actions second
3. UI automation last

Use typed node actions when:
- a browser workflow is not the right surface
- the action is local to Cory's Mac
- the action can be described narrowly with typed inputs and expected proof

Do not use this model as a disguised wrapper around unrestricted shell execution.

## Action Contract

Every typed action must define:
- `action_id`
- `summary`
- `inputs`
- `approval_class`
- `proof_required`
- `result_shape`
- `failure_behavior`

Recommended packet fields:
- `Device Target:`
- `Action Class:`
- `Action Id:`
- `Inputs Summary:`
- `Evidence Required:`
- `Rollback:`

## Approval Classes

- `read_like`
  - low-risk inspection or navigation with no persistent state change
- `local_write`
  - local state changes that are reversible or bounded
- `identity_bearing`
  - actions that use Cory's accounts, live apps, or personal session context
- `destructive`
  - deletes, overwrites, or irreversible modifications
- `persistent_change`
  - host/gateway behavior changes that outlive the current task

Default rule:
- `read_like` may proceed with proof
- all other classes require explicit approval unless a narrower policy later says otherwise

## Initial Verb Set

### `open_app`

- **Summary**: Launch a known macOS application by bundle id or app name.
- **Inputs**:
  - `app_name` or `bundle_id`
  - optional `args`
- **Approval Class**: `read_like`
- **Proof Required**:
  - launched app identifier
  - timestamp
  - optional screenshot when the app launch is part of a visible workflow
- **Result Shape**:
  - `status`
  - `app_name`
  - `bundle_id`
  - `launched`
- **Failure Behavior**:
  - return `failed`
  - include missing app or launch error
  - do not fall back to broad shell logic

### `open_url`

- **Summary**: Open a URL using the default browser or a specified browser target.
- **Inputs**:
  - `url`
  - optional `browser`
- **Approval Class**: `read_like`
- **Proof Required**:
  - normalized URL
  - target browser
  - timestamp
- **Result Shape**:
  - `status`
  - `url`
  - `browser`
- **Failure Behavior**:
  - fail closed on invalid URL
  - do not silently redirect to a different app or browser

### `notify`

- **Summary**: Trigger a local notification on Cory's Mac.
- **Inputs**:
  - `title`
  - `body`
  - optional `subtitle`
- **Approval Class**: `read_like`
- **Proof Required**:
  - notification payload summary
  - timestamp
- **Result Shape**:
  - `status`
  - `title`
- **Failure Behavior**:
  - return delivery failure
  - do not retry indefinitely without PULSE scheduling context

### `finder_reveal`

- **Summary**: Reveal a file or folder in Finder.
- **Inputs**:
  - `path`
- **Approval Class**: `local_write`
  - rationale: it changes local UI state and may expose sensitive files on screen
- **Proof Required**:
  - resolved path
  - existence check
  - timestamp
- **Result Shape**:
  - `status`
  - `path`
  - `exists`
- **Failure Behavior**:
  - return path resolution failure
  - do not guess alternate paths

### `shortcut`

- **Summary**: Run an allowlisted Apple Shortcut with typed arguments.
- **Inputs**:
  - `shortcut_name`
  - optional `input_payload`
- **Approval Class**: `local_write`
  - may be `identity_bearing` depending on the shortcut target
- **Proof Required**:
  - shortcut name
  - argument summary
  - exit result
- **Result Shape**:
  - `status`
  - `shortcut_name`
  - `output_summary`
- **Failure Behavior**:
  - return shortcut execution failure
  - do not substitute a shell command path

### `applescript`

- **Summary**: Execute a bounded, reviewed AppleScript template for a specific app or action.
- **Inputs**:
  - `template_id`
  - typed template parameters
- **Approval Class**: `identity_bearing`
  - may escalate to `destructive` or `persistent_change` depending on template intent
- **Proof Required**:
  - template id
  - parameter summary
  - app target
  - structured result or failure
- **Result Shape**:
  - `status`
  - `template_id`
  - `target_app`
  - `result_summary`
- **Failure Behavior**:
  - fail closed
  - do not execute arbitrary inline AppleScript by default

## Deferred Verbs

These are in scope for later typed expansion, but not the first implementation slice:
- `notes_create`
- `calendar_capture`
- `mail_compose`
- `mail_draft_attach`
- `reminders_create`

Each deferred verb must still follow the same typed contract and approval class model.

## Explicit Non-Goals

The first typed-action slice must not:
- expose a generic `shell` or `run_command` verb
- accept arbitrary inline AppleScript as a normal path
- hide multi-step workflows behind a single vague action id
- imply completion without proof

## Routing Expectations

- ORION decides whether the workflow should execute.
- ATLAS owns execution planning and proof requirements.
- STRATUS owns the adapter or host-side implementation details when local host integration is needed.
- PULSE may schedule or retry bounded typed actions only when the packet is explicit and approval posture is already satisfied.

## Failure and Retry Model

- Fail closed on invalid parameters, missing apps, invalid paths, or missing approvals.
- Return `pending approval` when the action class requires explicit approval and none is present.
- PULSE may retry only idempotent actions that are explicitly marked retry-safe.
- Do not auto-retry identity-bearing, destructive, or persistent-change actions.

## Proof Model

Minimum proof for typed node actions:
- action id
- device target
- parameter summary
- timestamp
- structured result
- relevant artifact path when applicable

ORION must use this proof model before reporting `verified`.
