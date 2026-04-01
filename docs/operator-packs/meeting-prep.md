# Operator Pack: Meeting Prep

## Purpose

Prepare a meeting workspace by gathering browser context, opening relevant tabs, and staging local follow-up artifacts for Cory before the meeting starts.

## Owners

- Primary: `ATLAS`
- Prep/support: `POLARIS`
- Retrieval support: `WIRE` for current participant/company/project context
- Gatekeeper: `ORION`

## Browser Lane

- Default lane: `managed-browser`
- Allowed companion lane: typed `macos-node` actions only when needed for local notes or file reveal

## Workflow Shape

1. POLARIS identifies the meeting target, time, and preparation objective.
2. WIRE optionally gathers current external context if recent facts matter.
3. ATLAS opens and arranges the relevant browser tabs:
   - calendar event
   - meeting doc
   - participant/company context
   - related project tracker or notes
4. ATLAS stages a prep summary or note reference.
5. ORION reports the prepared workspace and any remaining approval gates.

## What Can Be Automated

- open event links and related docs
- gather meeting context from known sources
- open tabs in a usable order
- stage a prep summary
- reveal a local prep note through a typed node action if explicitly included in the packet

## Approval Gates

Explicit approval required for:
- sending follow-up emails or chat messages
- editing shared docs in ways that change record
- using a personal browser session when not explicitly requested

## Inputs

- meeting title or URL
- event time
- participant or company names
- related project/doc links
- optional note destination

## Outputs

- prepared tab set
- short prep summary
- optional local note or file reveal
- proof bundle

## Proof Bundle

- URLs of opened meeting resources
- screenshot of prepared browser state
- summary of staged prep items
- local artifact path when a node action was used

## Failure Modes

- missing event/document links
- insufficient current context
- auth/session failures
- local artifact requested without typed node support

Required status language:
- `queued` or `in progress` while resources are being assembled
- `pending verification` if tabs were likely opened but proof is incomplete

## Example Packet Intent

- `Device Target: managed-browser`
- `Action Class: identity_bearing`
- `Action Id: meeting_prep_stage`
