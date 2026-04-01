# Direct Interaction Approvals And Proof

This document defines the approval ladder and proof bundle contract for ORION direct device interaction.

It applies to:
- browser-led direct interaction
- typed macOS node actions
- scheduled prep flows that queue or stage device work

## Status Language Contract

ORION should use these status words consistently:

- `pending approval`
  - the requested action needs Cory's approval before execution
- `queued`
  - the work is accepted but not started yet
- `in progress`
  - execution started, but the proof bundle is not complete yet
- `pending verification`
  - execution likely happened, but ORION does not yet have enough proof to report `verified`
- `verified`
  - the action completed and the proof bundle is present
- `failed`
  - the action did not complete successfully

Do not use `done`, `complete`, or similar language for direct interaction unless the proof bundle supports `verified`.

## Approval Ladder

### Level A: `read_like`

Examples:
- open a URL
- open an app
- local notification
- read-only browser inspection
- navigate to a page without submitting changes

Policy:
- may proceed without extra approval
- must still return proof

### Level B: `local_write`

Examples:
- reveal a file in Finder
- run a bounded shortcut
- change local UI state in a reversible way

Policy:
- default to requiring explicit approval unless the action is clearly routine, reversible, and already expected by the workflow
- if approval is ambiguous, ORION should stop and ask
- proof is required

### Level C: `identity_bearing`

Examples:
- actions inside a live authenticated browser session
- account-linked AppleScript templates
- draft creation in apps tied to Cory's identity

Policy:
- explicit approval required before execution
- browser flows should stage before send/submit whenever possible
- proof is required

### Level D: `destructive`

Examples:
- delete, overwrite, or irreversible modification
- closing or dismissing artifacts in a way that loses user state

Policy:
- explicit approval required
- reversible first step required when possible
- proof is required

### Level E: `persistent_change`

Examples:
- enabling remote access
- changing gateway behavior
- enabling Mini App command routing
- installing persistent host automation

Policy:
- explicit approval required
- change must be described clearly before execution
- proof is required

## Approval Prompt Shape

When approval is required, ORION should include:
- what it plans to do
- which device lane it will use
- the stop gate or risk category
- what proof it will return

Preferred shape:

```text
This needs approval before I execute it.
Plan:
- <specific action>
- Lane: <managed-browser | personal-browser | macos-node>
- Risk: <identity-bearing | destructive | persistent_change | local_write>
Proof I will return:
- <artifact 1>
- <artifact 2>
```

## Proof Bundle Contract

Every direct-interaction workflow should return a proof bundle with:
- `device_target`
- `action_class`
- `action_id` or workflow id
- `approval_state`: `approved` | `not_required` | `pending`
- `status`: `verified` | `pending verification` | `failed`
- `summary`
- `artifacts`

Recommended artifacts:
- screenshot path
- URL or browser target
- structured result payload
- relevant local path
- command or adapter log path when applicable

## Minimal Proof By Lane

### Managed browser
- target URL
- screenshot or equivalent visual artifact
- final action summary

### Personal browser
- explicit note that the live personal session was used
- URL or tab target
- screenshot or structured result

### macOS node
- action id
- parameter summary
- structured result
- timestamp

## Failure Handling

- If approval is missing, return `pending approval`.
- If execution happens but artifacts are incomplete, return `pending verification`.
- If execution fails, return `failed` with the reason and next step.
- Do not silently promote `pending verification` to `verified`.

## Scheduling Rule

Cron/hooks may:
- gather context
- stage work
- create approval queues

Cron/hooks may not:
- auto-run approval-gated direct interaction without explicit approval already present
- imply that staged work is already `verified`
