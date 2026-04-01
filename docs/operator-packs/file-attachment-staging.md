# Operator Pack: File And Attachment Staging

## Purpose

Prepare local files for later browser-led or email-led workflows by revealing the file, validating the target path, and staging the attachment context without sending or uploading by default.

## Owners

- Primary: `ATLAS`
- Host-side implementation: `STRATUS`
- Prep/support: `POLARIS`
- Gatekeeper: `ORION`

## Device Lane

- Default lane: `macos-node`
- Allowed typed actions:
  - `finder_reveal`
  - `open_app` when the staging flow requires the target app to be visible

## Workflow Shape

1. POLARIS or ORION identifies the intended file and target workflow.
2. ATLAS validates that the workflow is still in the staging phase.
3. STRATUS performs the typed local actions.
4. ORION reports the staged file context and any remaining approval gates before upload/send.

## What Can Be Automated

- reveal a file or folder in Finder
- open the related app if that helps stage the file
- confirm the intended path exists
- prepare local context before a later upload step

## Approval Gates

Explicit approval required for:
- uploading the file into a portal
- sending the file by email or chat
- revealing sensitive local paths when the target file is ambiguous

## Inputs

- file path or folder path
- target downstream workflow
- optional app target
- explicit scope such as `reveal only`

## Outputs

- revealed file context
- existence check
- proof bundle
- missing-path or ambiguity report if needed

## Proof Bundle

- action ids used
- resolved path
- exists flag
- timestamp
- optional screenshot when visible review matters

## Failure Modes

- missing file
- ambiguous target path
- downstream workflow implies upload/send without approval

Required status language:
- `pending approval` when the request implicitly crosses into upload/send
- `pending verification` when a visible reveal likely occurred but only partial proof was returned

## Example Packet Intent

- `Device Target: macos-node`
- `Action Class: local_write`
- `Action Id: file_attachment_stage`
