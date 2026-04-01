# Operator Packs

These operator packs define repeatable, browser-led workflows for ORION.

They are workflow contracts, not blanket permission to act autonomously.

Each pack must:
- prefer the managed browser lane
- use explicit Task Packets
- declare staged vs approval-gated actions
- return proof bundles before ORION reports `verified`

## Current Packs

- [inbox-triage.md](/Users/corystoner/Desktop/ORION/docs/operator-packs/inbox-triage.md)
- [meeting-prep.md](/Users/corystoner/Desktop/ORION/docs/operator-packs/meeting-prep.md)
- [portal-staging.md](/Users/corystoner/Desktop/ORION/docs/operator-packs/portal-staging.md)
- [app-and-note-setup.md](/Users/corystoner/Desktop/ORION/docs/operator-packs/app-and-note-setup.md)
- [file-attachment-staging.md](/Users/corystoner/Desktop/ORION/docs/operator-packs/file-attachment-staging.md)
- [local-notify-shortcut-prep.md](/Users/corystoner/Desktop/ORION/docs/operator-packs/local-notify-shortcut-prep.md)

## Shared Rules

- Use [docs/DEVICE_INTERACTION_POLICY.md](/Users/corystoner/Desktop/ORION/docs/DEVICE_INTERACTION_POLICY.md) for lane selection.
- Use [docs/DIRECT_INTERACTION_APPROVALS.md](/Users/corystoner/Desktop/ORION/docs/DIRECT_INTERACTION_APPROVALS.md) for approval and proof status.
- Use [docs/TASK_PACKET.md](/Users/corystoner/Desktop/ORION/docs/TASK_PACKET.md) for packet shape.
- Default owner for browser-led packs is `ATLAS`.
- Use `WIRE` when current external information is needed.
- Use `POLARIS` when admin preparation or follow-through structure is part of the workflow.
