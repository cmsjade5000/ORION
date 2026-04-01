# Operator Pack: Portal Submission Staging

## Purpose

Stage work inside authenticated web portals without crossing the final submit/pay/send boundary until Cory approves it.

Typical targets:
- expense portals
- reimbursement systems
- admin dashboards
- application forms

## Owners

- Primary: `ATLAS`
- Prep/support: `POLARIS`
- Gatekeeper: `ORION`

## Browser Lane

- Default lane: `managed-browser`
- Personal browser relay: only by explicit request

## Workflow Shape

1. ORION or POLARIS defines the portal task and stop gate.
2. ATLAS opens the target portal in the managed browser.
3. ATLAS navigates to the relevant draft or form.
4. ATLAS fills or stages the allowed fields.
5. ATLAS stops before submit/pay/send and returns proof.
6. ORION asks for approval if the user wants the final action executed.

## What Can Be Automated

- login-adjacent navigation once authenticated context exists
- form navigation
- field population from approved inputs
- attachment staging when explicitly provided
- draft save or stage-for-review actions

## Approval Gates

Explicit approval required for:
- submit
- pay
- send
- account-setting changes
- attachment upload from sensitive local paths unless clearly specified in the packet

## Inputs

- portal target
- record id or form target
- allowed fields to populate
- attachment paths if any
- explicit stop gate

## Outputs

- staged draft or form state
- missing-input list
- approval checkpoint
- proof bundle

## Proof Bundle

- current portal URL
- screenshot of staged form/draft
- field summary or staged-state summary
- attachment list if staged

## Failure Modes

- auth/session issues
- missing required inputs
- sensitive attachment ambiguity
- portal changed structure

Required status language:
- `pending approval` at the final submit/pay/send boundary
- `failed` when the portal cannot be staged safely

## Example Packet Intent

- `Device Target: managed-browser`
- `Action Class: identity_bearing`
- `Action Id: portal_submission_stage`
