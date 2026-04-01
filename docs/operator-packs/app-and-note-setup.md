# Operator Pack: App And Note Setup

## Purpose

Prepare Cory's local workspace by opening the relevant app, revealing or staging the right note/document context, and stopping before content changes that require approval.

## Owners

- Primary: `ATLAS`
- Host-side implementation: `STRATUS`
- Prep/support: `POLARIS`
- Gatekeeper: `ORION`

## Device Lane

- Default lane: `macos-node`
- Allowed typed actions:
  - `open_app`
  - `finder_reveal`
  - bounded `applescript` only if a reviewed template exists

## Workflow Shape

1. POLARIS or ORION identifies the app and note/document target.
2. ATLAS builds the typed action sequence.
3. STRATUS executes the host-side adapter calls if needed.
4. ORION reports the prepared local workspace and any approval gates.

## What Can Be Automated

- open a known application
- reveal a known folder or file
- bring a reviewed note/document context into view
- stage local workspace state for Cory

## Approval Gates

Explicit approval required for:
- editing note or document contents
- using a bounded AppleScript template that touches identity-bearing app state
- any action that goes beyond opening/revealing/staging local context

## Inputs

- target app
- file or folder path
- optional note/document identifier
- explicit scope such as `open only` or `reveal only`

## Outputs

- prepared local app state
- visible file/note context
- proof bundle

## Proof Bundle

- action ids used
- app identifier
- resolved path if applicable
- timestamp
- structured result payload

## Failure Modes

- app not installed
- invalid path
- missing reviewed AppleScript template
- action requires approval that is not present

Required status language:
- `pending approval` when the request crosses from staging into editing
- `failed` when the local target cannot be resolved safely

## Example Packet Intent

- `Device Target: macos-node`
- `Action Class: local_write`
- `Action Id: app_and_note_setup`
