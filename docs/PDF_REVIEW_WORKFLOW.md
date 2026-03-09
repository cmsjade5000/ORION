# PDF Review Workflow

OpenClaw `2026.3.2` adds two capabilities that fit ORION directly:

- first-class `pdf` analysis
- inline file attachments for `sessions_spawn` subagent runs

Use this workflow when Cory gives ORION a PDF, slide deck, contract, report, or other file-heavy artifact that is better inspected by a specialist than summarized inline.

## Goals

- Keep ORION as the only user-facing messenger.
- Let specialists inspect the source artifact directly.
- Avoid storing sensitive attachments in the repo.

## Preferred Flow

1. ORION receives the user request and identifies the right specialist.
2. ORION creates a `TASK_PACKET v1` with the review objective, success criteria, and stop gates.
3. ORION calls `sessions_spawn` and passes the source file as an inline attachment.
4. OpenClaw materializes the attachment into the child workspace under `.openclaw/attachments/`.
5. The specialist uses the `pdf` tool when the source is a PDF, or the relevant file-aware toolchain otherwise.
6. The specialist returns an internal result to ORION only.
7. ORION sends one integrated summary back to Cory.

## Constraints

- Attachments are for subagent runtime only; do not assume ACP sessions can consume them.
- Do not copy sensitive PDFs or attachments into the repository.
- Prefer summary artifacts over raw document dumps.
- If the file contains secrets or private data, keep the response high-signal and minimally quoted.

## Suggested Task Packet Additions

Use these fields when a file is central to the task:

- `Execution Mode: delegate`
- `Tool Scope: read-only`
- `Evidence Required:` summary + file path used + validation notes
- `Inputs:` include the original local file path and the user request

## Example Packet Shape

```text
TASK_PACKET v1
Owner: SCRIBE
Requester: ORION
Objective: Review the attached quarterly report PDF and extract the top risks, decisions, and missing evidence.
Success Criteria:
- Identifies the top findings with page references when available.
- Calls out any missing inputs or unresolved claims.
Constraints:
- Read-only review.
- Do not deliver directly to Telegram.
Inputs:
- User request text
- Attached PDF via sessions_spawn
Risks:
- low
Stop Gates:
- Any recommendation that depends on unverified numbers.
Output Format:
- Short findings list + recommended next step
```

## Verification

- Validate runtime config before use: `openclaw config validate --json`
- Confirm the relevant specialist is allowlisted for `sessions_spawn`.
- When troubleshooting, verify attachment support and limits in the OpenClaw config reference.
