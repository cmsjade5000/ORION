## Packets

TASK_PACKET v1
Owner: AEGIS_PLAN_WATCH_DELEGATION
Requester: ORION
Objective: Poll AEGIS for new HITL plans (defense/maintenance) and notify the Telegram group chat.
Success Criteria:
- If new plans are detected, sends a concise Telegram message per new plan.
- If no new plans are detected, exits quietly.
Constraints:
- Do not execute any defensive action, fixes, updates, commits, pushes, or restarts.
- Notification only.
Inputs:
- Script: /Users/corystoner/Desktop/ORION/scripts/aegis_defense_watch.sh
- Environment Variable: ORION_TELEGRAM_CHAT_ID=-5007679487
Risks:
- Potential notification spam if state resets; mitigated by tmp state file.
Stop Gates:
- Any action that changes security posture.
Output Format:
- Return a concise status with: plans_checked, new_plans_count, and any notification delivery errors.
