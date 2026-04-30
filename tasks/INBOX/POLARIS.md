# POLARIS Inbox

POLARIS is internal-only. ORION assigns admin co-pilot workflows here.

Scope examples:
- reminders/calendar workflow orchestration
- contact organization and follow-through tracking
- email-prep packet coordination
- daily agenda prep and quick capture triage

Append new Task Packets below. Spec: `docs/TASK_PACKET.md`.

Queue policy (enforced):
- Max active packets in this inbox: 8.
- Age bands: `0-24h` normal, `>24h` amber, `>48h` red, `>72h` gatekeeper escalation, `>120h` incident required.
- Backup takeover and gatekeeper authority follow `docs/AGENT_OWNERSHIP_MATRIX.md`.

Milestone update protocol:
- For rollout/admin packets that should notify Cory, include `Notify: telegram`.
- Keep milestone labels bounded:
  - `Scaffold complete`
  - `Routing + gates complete`
  - `Tests green + config active`

Required admin fields for new POLARIS packets:
- `Notify: telegram`
- `Opened: YYYY-MM-DD`
- `Due: YYYY-MM-DD`
- `Execution Mode: direct|delegate`
- `Tool Scope: read-only|write`

Canonical packet shapes:
- `docs/POLARIS_ADMIN_WORKFLOWS.md`

## Weekly Routing Audit Runbook

Run location:
- ORION main workspace session at `/Users/corystoner/src/ORION`.

Cadence:
- Weekly (Friday ET recommended).

ORION report format (concise):
- `Queue: <active>/<max> (max=8), oldest=<age>`
- `Aging bands: >24h=<n>, >48h=<n>, >72h=<n>, >120h=<n>`
- `Escalations: <none|list>`
- `Routing fixes: <none|list>`
- `Next actions: <1-3 bullets>`

## Packets
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-30
Due: 2026-05-02
Execution Mode: direct
Tool Scope: read-only
Objective: Triage and file Cory's captured admin item into the correct assistant workflow.
Success Criteria:
- The capture is classified (reminder, note, follow-up, agenda item, or email-prep).
- The next safe step is identified without taking external side effects.
- ORION can follow up with a concise status update.
Constraints:
- Prepare/draft first; do not create external records without explicit approval.
- Keep all changes local to repo artifacts unless ORION relays approval.
Inputs:
- tasks/INTAKE/2026-04-30-122607-follow-up-on-delegated-orion-work-owner-atlas-st.md
- Capture text:
  Follow up on delegated ORION work.
  Owner: ATLAS
  State: blocked
  Objective: Translate inbound ops request into a safe execution plan with explicit stop gates.
  Inbox: tasks/INBOX/ATLAS.md:83
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.

Result:
Status: OK
Classification: follow-up
What changed / what I found:
- Reviewed the intake capture and the referenced ATLAS packet at `tasks/INBOX/ATLAS.md:83`.
- The captured item is best filed as a follow-up, not a reminder or agenda item, because it points to already-delegated work and asks for status/action on a blocked packet.
- The referenced ATLAS work is blocked on explicit Cory approval before any side-effecting execution can occur.
Proposed next step:
- ORION should give Cory a concise follow-up that the delegated ATLAS packet is blocked pending explicit approval for the underlying side-effecting action, and ask whether to approve or leave it parked.
Approval gate:
- Yes — explicit Cory approval is required before the blocked ATLAS packet can proceed.
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-30
Due: 2026-05-02
Execution Mode: direct
Tool Scope: read-only
Objective: Triage and file Cory's captured admin item into the correct assistant workflow.
Success Criteria:
- The capture is classified (reminder, note, follow-up, agenda item, or email-prep).
- The next safe step is identified without taking external side effects.
- ORION can follow up with a concise status update.
Constraints:
- Prepare/draft first; do not create external records without explicit approval.
- Keep all changes local to repo artifacts unless ORION relays approval.
Inputs:
- tasks/INTAKE/2026-04-30-125215-follow-up-on-delegated-orion-work-owner-atlas-st.md
- Capture text:
  Follow up on delegated ORION work.
  Owner: ATLAS
  State: blocked
  Objective: TEST APPROVAL: confirm Mini App approval flow for a dry-run ATLAS packet.
  Inbox: tasks/INBOX/ATLAS.md:139
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.

Result:
Status: OK
Classification: email-prep
Proposed next step:
- Prepare a draft or approval question only; do not send email until ORION has explicit approval and send proof.
Approval gate:
- Required before any external send, calendar write, reminder write, or destructive edit.
Evidence:
- Intake: tasks/INTAKE/2026-04-30-125215-follow-up-on-delegated-orion-work-owner-atlas-st.md

TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-30
Due: 2026-05-02
Execution Mode: direct
Tool Scope: read-only
Objective: Triage and file Cory's captured admin item into the correct assistant workflow.
Success Criteria:
- The capture is classified (reminder, note, follow-up, agenda item, or email-prep).
- The next safe step is identified without taking external side effects.
- ORION can follow up with a concise status update.
Constraints:
- Prepare/draft first; do not create external records without explicit approval.
- Keep all changes local to repo artifacts unless ORION relays approval.
Inputs:
- tasks/INTAKE/2026-04-30-125240-follow-up-on-delegated-orion-work-owner-atlas-st.md
- Capture text:
  Follow up on delegated ORION work.
  Owner: ATLAS
  State: blocked
  Objective: TEST APPROVAL: confirm Mini App deny path for a Task Packet.
  Inbox: tasks/INBOX/ATLAS.md:170
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.

Result:
Status: OK
Classification: email-prep
Proposed next step:
- Prepare a draft or approval question only; do not send email until ORION has explicit approval and send proof.
Approval gate:
- Required before any external send, calendar write, reminder write, or destructive edit.
Evidence:
- Intake: tasks/INTAKE/2026-04-30-125240-follow-up-on-delegated-orion-work-owner-atlas-st.md
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-30
Due: 2026-05-02
Execution Mode: direct
Tool Scope: read-only
Objective: Triage and file Cory's captured admin item into the correct assistant workflow.
Success Criteria:
- The capture is classified (reminder, note, follow-up, agenda item, or email-prep).
- The next safe step is identified without taking external side effects.
- ORION can follow up with a concise status update.
Constraints:
- Prepare/draft first; do not create external records without explicit approval.
- Keep all changes local to repo artifacts unless ORION relays approval.
Inputs:
- tasks/INTAKE/2026-04-30-130100-follow-up-on-delegated-orion-work-owner-atlas-st.md
- Capture text:
  Follow up on delegated ORION work.
  Owner: ATLAS
  State: blocked
  Objective: TEST APPROVAL: verify visible approved-state feedback in the Mini App.
  Inbox: tasks/INBOX/ATLAS.md:237
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.

Result:
Status: OK
Classification: email-prep
Proposed next step:
- Prepare a draft or approval question only; do not send email until ORION has explicit approval and send proof.
Approval gate:
- Required before any external send, calendar write, reminder write, or destructive edit.
Evidence:
- Intake: tasks/INTAKE/2026-04-30-130100-follow-up-on-delegated-orion-work-owner-atlas-st.md
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-30
Due: 2026-05-02
Execution Mode: direct
Tool Scope: read-only
Objective: Triage and file Cory's captured admin item into the correct assistant workflow.
Success Criteria:
- The capture is classified (reminder, note, follow-up, agenda item, or email-prep).
- The next safe step is identified without taking external side effects.
- ORION can follow up with a concise status update.
Constraints:
- Prepare/draft first; do not create external records without explicit approval.
- Keep all changes local to repo artifacts unless ORION relays approval.
Inputs:
- tasks/INTAKE/2026-04-30-155233-follow-up-on-delegated-orion-work-owner-atlas-st.md
- Capture text:
  Follow up on delegated ORION work.
  Owner: ATLAS
  State: blocked
  Objective: TEST APPROVAL: verify visible denied-state feedback in the Mini App.
  Inbox: tasks/INBOX/ATLAS.md:268
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.

Result:
Status: OK
Classification: email-prep
Proposed next step:
- Prepare a draft or approval question only; do not send email until ORION has explicit approval and send proof.
Approval gate:
- Required before any external send, calendar write, reminder write, or destructive edit.
Evidence:
- Intake: tasks/INTAKE/2026-04-30-155233-follow-up-on-delegated-orion-work-owner-atlas-st.md

TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-30
Due: 2026-05-02
Execution Mode: direct
Tool Scope: read-only
Objective: Triage and file Cory's captured admin item into the correct assistant workflow.
Success Criteria:
- The capture is classified (reminder, note, follow-up, agenda item, or email-prep).
- The next safe step is identified without taking external side effects.
- ORION can follow up with a concise status update.
Constraints:
- Prepare/draft first; do not create external records without explicit approval.
- Keep all changes local to repo artifacts unless ORION relays approval.
Inputs:
- tasks/INTAKE/2026-04-30-155234-follow-up-on-delegated-orion-work-owner-atlas-st.md
- Capture text:
  Follow up on delegated ORION work.
  Owner: ATLAS
  State: blocked
  Objective: Translate inbound ops request into a safe execution plan with explicit stop gates.
  Inbox: tasks/INBOX/ATLAS.md:50
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.

Result:
Status: OK
Classification: email-prep
Proposed next step:
- Prepare a draft or approval question only; do not send email until ORION has explicit approval and send proof.
Approval gate:
- Required before any external send, calendar write, reminder write, or destructive edit.
Evidence:
- Intake: tasks/INTAKE/2026-04-30-155234-follow-up-on-delegated-orion-work-owner-atlas-st.md
