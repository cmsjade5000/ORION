# ORION File Transfer Broker

## Purpose

ORION may use OpenClaw's bundled `file-transfer` plugin only as a brokered node handoff surface.
It is not a freeform node-to-node file movement system.

The broker keeps ORION as user-facing ingress, routes execution through ATLAS, preserves Task Packet
evidence, and limits reads and writes to explicit staging and artifact paths.

## Ownership

- ORION receives the request and decides whether file movement is warranted.
- ATLAS owns multi-step transfer execution.
- STRATUS may handle node, host, and gateway implementation details under ATLAS.
- ORION sends the final user-facing status only after proof is available.

Allowed operations:

- `dir_list`
- `file_fetch`
- `dir_fetch`
- `file_write`

## Path Policy

The live runtime must resolve the paired Mac Mini node ID and write policy under that stable node ID.
Do not use a wildcard `*` node policy.

Required node policy:

- `ask: always`
- `followSymlinks: false`
- `maxBytes: 16777216`
- `gateway.nodes.allowCommands` limited to `dir.list`, `file.fetch`, `dir.fetch`, and `file.write`

Allowed read paths:

- `/Users/corystoner/src/ORION/tmp/file-transfer-broker/outbound/**`
- `/Users/corystoner/src/ORION/tasks/WORK/artifacts/**`
- `/Users/corystoner/src/ORION/tasks/JOBS/**`
- `/Users/corystoner/.openclaw/attachments/**`

Allowed write paths:

- `/Users/corystoner/src/ORION/tmp/file-transfer-broker/inbound/**`

Hard denied paths:

- `/Users/corystoner/.openclaw/secrets/**`
- `/Users/corystoner/.openclaw/.env*`
- `/Users/corystoner/.ssh/**`
- `/Users/corystoner/Library/Keychains/**`
- `/Users/corystoner/Library/**`
- `/Users/corystoner/src/ORION/.git/**`

## Task Packet Requirements

Every brokered transfer needs a Task Packet with:

- `Owner: ATLAS`
- `Device Target: macos-node`
- `Action Class: read_like` for `dir_list`, `file_fetch`, and `dir_fetch`
- `Action Class: local_write` for `file_write`
- `Action Id: file_fetch | dir_list | dir_fetch | file_write`
- `Inputs Summary:` source path, destination path when relevant, and node display name
- `Approval Gate: CORY_MINIAPP_APPROVED` for writes
- `Evidence Required:` source path, destination path, command/result payload, and final listing or checksum when available
- `Rollback:` exact cleanup or restore step for write flows

## Reporting

ORION must report transfer state as `verified`, `pending verification`, or `failed`.
Do not claim a file was moved, fetched, or written unless the command result and final path/checksum proof were observed in the same workflow.
