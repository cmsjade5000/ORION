# Operator Pack: Inbox Triage

## Purpose

Use the managed browser to review inbox-like queues, classify items, and stage follow-up work without sending or archiving approval-gated content by default.

Typical targets:
- Gmail
- support queues
- dashboard inboxes

## Owners

- Primary: `ATLAS`
- Prep/support: `POLARIS`
- Retrieval support: `WIRE` when current external context is needed
- Gatekeeper: `ORION`

## Browser Lane

- Default lane: `managed-browser`
- Personal browser relay: only if Cory explicitly wants actions in an already-open live session

## Workflow Shape

1. POLARIS or ORION defines the inbox scope.
2. ATLAS opens the target inbox in the managed browser.
3. ATLAS reviews the relevant items and groups them:
   - informational
   - draft-needed
   - needs reply approval
   - needs follow-up task
4. ATLAS stages drafts, labels, or queue notes where policy allows.
5. ORION reports the staged outcomes and any approval gates.

## What Can Be Automated

- open the inbox
- navigate folders/labels/views
- gather message subjects and metadata
- group items by action needed
- draft replies without sending
- stage follow-up notes or task suggestions

## Approval Gates

Explicit approval required for:
- sending replies
- archiving or deleting content in bulk
- changing account settings
- acting inside a live personal browser session unless that was explicitly requested

## Inputs

- inbox target
- time window or label/folder
- triage objective
- optional constraints such as `draft only` or `no archive`

## Outputs

- triage summary
- draft list
- approval queue items
- proof bundle

## Proof Bundle

- target inbox URL or location
- screenshot of staged state
- summary of classified items
- draft references or note paths when applicable

## Failure Modes

- session/auth problem
- ambiguous inbox scope
- unsafe action requested without approval
- proof incomplete after browser interaction

Required status language:
- `pending approval` for send/archive gates
- `pending verification` if staging likely happened but proof is incomplete

## Example Packet Intent

- `Device Target: managed-browser`
- `Action Class: identity_bearing`
- `Action Id: inbox_triage_stage`
