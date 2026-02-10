# EMBER Inbox

Append new Task Packets below. Spec: `docs/TASK_PACKET.md`.

Constraints reminder:
- Never diagnose.
- Never replace professional care.
- If crisis signals appear, prioritize safety.

## Packets

```text
TASK_PACKET v1
Owner: EMBER
Requester: ORION
Objective: Provide a short spoken calming script for Cory to hear as an audio attachment.
Success Criteria:
- Returns a TTS-ready script with preset + duration target using the specified output format.
Constraints:
- No diagnosis, no medical instructions.
- Preserve agency and choice.
- If driving/unsafe context, avoid "close your eyes" and include a safety note.
Inputs:
- User context: <paste Cory's message + any constraints like "30s" / "urgent" / "can't sleep">
Risks:
- User may be in crisis; if crisis/self-harm signals appear, prioritize safety guidance.
Stop Gates:
- Crisis/self-harm intent: do not produce "soothing audio" as a substitute for safety steps.
Output Format:
- TTS_PRESET:
- TTS_VOICE_HINT:
- DURATION_SEC_TARGET:
- SCRIPT:
- SAFETY_NOTE:
```
