# Operator Pack: Local Notify And Shortcut Prep

## Purpose

Use low-risk local notifications and bounded shortcuts to prepare Cory's environment for a task without executing higher-risk identity-bearing or persistent actions.

## Owners

- Primary: `ATLAS`
- Host-side implementation: `STRATUS`
- Scheduling/queue support: `PULSE`
- Gatekeeper: `ORION`

## Device Lane

- Default lane: `macos-node`
- Allowed typed actions:
  - `notify`
  - `shortcut`

## Workflow Shape

1. ORION or POLARIS defines the prep objective.
2. ATLAS classifies whether the shortcut is `local_write` or escalates to `identity_bearing`.
3. STRATUS executes the typed action if approval posture is satisfied.
4. PULSE may schedule or retry only when the action is explicitly retry-safe.
5. ORION reports the result and proof bundle.

## What Can Be Automated

- send a local notification
- run a reviewed, allowlisted shortcut
- prepare a task prompt or reminder locally

## Approval Gates

Explicit approval required for:
- shortcuts that interact with identity-bearing apps or accounts
- shortcuts that change durable host or gateway behavior
- repeated scheduled execution unless the workflow was explicitly approved

## Inputs

- notification payload or shortcut name
- optional shortcut input payload
- schedule/retry context if any

## Outputs

- delivered notification or shortcut result
- proof bundle
- retry-safe classification when applicable

## Proof Bundle

- action id
- notification or shortcut summary
- timestamp
- structured output summary

## Failure Modes

- notification delivery failure
- unknown shortcut
- shortcut behavior exceeds approved scope
- schedule requested for a non-retry-safe action

Required status language:
- `pending approval` for identity-bearing shortcut runs
- `failed` when the shortcut is unknown or outside approved scope

## Example Packet Intent

- `Device Target: macos-node`
- `Action Class: local_write`
- `Action Id: local_notify_shortcut_prep`
