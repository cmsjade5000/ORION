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
Opened: 2026-04-28
Due: 2026-04-30
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
- tasks/INTAKE/2026-04-28-130301-follow-up-on-delegated-orion-work-owner-scribe-s.md
- Capture text: Follow up on delegated ORION work.
- Referenced packet owner: SCRIBE
- Referenced packet state: blocked
- Referenced packet objective: Create a send-ready draft response from the inbound request context.
- Referenced packet inbox: tasks/INBOX/SCRIBE.md:96
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-28
Due: 2026-04-30
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
- tasks/INTAKE/2026-04-28-130307-follow-up-on-delegated-orion-work-owner-scribe-s.md
- Capture text: Follow up on delegated ORION work.
- Referenced packet owner: SCRIBE
- Referenced packet state: blocked
- Referenced packet objective: Create a send-ready draft response from the inbound request context.
- Referenced packet inbox: tasks/INBOX/SCRIBE.md:96
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-28
Due: 2026-04-30
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
- tasks/INTAKE/2026-04-28-130311-follow-up-on-delegated-orion-work-owner-scribe-s.md
- Capture text: Follow up on delegated ORION work.
- Referenced packet owner: SCRIBE
- Referenced packet state: blocked
- Referenced packet objective: Create a send-ready draft response from the inbound request context.
- Referenced packet inbox: tasks/INBOX/SCRIBE.md:142
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-28
Due: 2026-04-30
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
- tasks/INTAKE/2026-04-28-130321-follow-up-on-delegated-orion-work-owner-scribe-s.md
- Capture text: Follow up on delegated ORION work.
- Referenced packet owner: SCRIBE
- Referenced packet state: blocked
- Referenced packet objective: Create a send-ready draft response from the inbound request context.
- Referenced packet inbox: tasks/INBOX/SCRIBE.md:96
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-28
Due: 2026-04-30
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
- tasks/INTAKE/2026-04-28-130326-follow-up-on-delegated-orion-work-owner-scribe-s.md
- Capture text: Follow up on delegated ORION work.
- Referenced packet owner: SCRIBE
- Referenced packet state: blocked
- Referenced packet objective: Create a send-ready draft response from the inbound request context.
- Referenced packet inbox: tasks/INBOX/SCRIBE.md:96
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-28
Due: 2026-04-30
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
- tasks/INTAKE/2026-04-28-130902-follow-up-on-delegated-orion-work-owner-scribe-s.md
- Capture text: Follow up on delegated ORION work.
- Referenced packet owner: SCRIBE
- Referenced packet state: blocked
- Referenced packet objective: Create a send-ready draft response from the inbound request context.
- Referenced packet inbox: tasks/INBOX/SCRIBE.md:142
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-28
Due: 2026-04-30
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
- tasks/INTAKE/2026-04-28-133259-follow-up-on-delegated-orion-work-owner-scribe-s.md
- Capture text: Follow up on delegated ORION work.
- Referenced packet owner: SCRIBE
- Referenced packet state: blocked
- Referenced packet objective: Create a send-ready draft response from the inbound request context.
- Referenced packet inbox: tasks/INBOX/SCRIBE.md:142
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-28
Due: 2026-04-30
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
- tasks/INTAKE/2026-04-28-133319-follow-up-on-delegated-orion-work-owner-scribe-s.md
- Capture text: Follow up on delegated ORION work.
- Referenced packet owner: SCRIBE
- Referenced packet state: blocked
- Referenced packet objective: Create a send-ready draft response from the inbound request context.
- Referenced packet inbox: tasks/INBOX/SCRIBE.md:96
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-28
Due: 2026-04-30
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
- tasks/INTAKE/2026-04-28-135130-follow-up-on-delegated-orion-work-owner-scribe-s.md
- Capture text: Follow up on delegated ORION work.
- Referenced packet owner: SCRIBE
- Referenced packet state: blocked
- Referenced packet objective: Create a send-ready draft response from the inbound request context.
- Referenced packet inbox: tasks/INBOX/SCRIBE.md:96
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.
TASK_PACKET v1
Owner: POLARIS
Requester: ORION
Notify: telegram
Opened: 2026-04-28
Due: 2026-04-30
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
- tasks/INTAKE/2026-04-28-135154-follow-up-on-delegated-orion-work-owner-scribe-s.md
- Capture text: Follow up on delegated ORION work.
- Referenced packet owner: SCRIBE
- Referenced packet state: blocked
- Referenced packet objective: Create a send-ready draft response from the inbound request context.
- Referenced packet inbox: tasks/INBOX/SCRIBE.md:142
Risks:
- low
Stop Gates:
- Any external send, calendar write, reminder write, or destructive edit.
Output Format:
- Result block with classification, proposed next step, and any approval gate.
