# Agent Autonomy Kit Implementation Plan

## T1: Scaffold Task Queue
- **depends_on:** []
- **description:** Create `tasks/QUEUE.md` with sections Ready, In Progress, Blocked, Done Today as per templates/QUEUE.md.

## T2: Update Heartbeat Routine
- **depends_on:** [T1]
- **description:** Replace passive `HEARTBEAT.md` with proactive work loop from templates/HEARTBEAT.md.

## T3: Integrate Templates
- **depends_on:** [T2]
- **description:** Copy `templates/HEARTBEAT.md` and `templates/QUEUE.md` into project root and ensure `skills/new-skill/SKILL.md` references them.

## T4: Configure Cron Jobs
- **depends_on:** [T3]
- **description:** Add cron jobs for proactive heartbeats (every 15m), morning kickoff (7:00), and daily report (22:00) using `openclaw cron add` as defined in README.md.

## T5: Team Channel Setup
- **depends_on:** [T4]
- **description:** Update openclaw.yaml (or channels config) to add a team channel group for Agent Autonomy Kit notifications.

## T6: Validation & Smoke Test
- **depends_on:** [T5]
- **description:** Run `tasks/QUEUE.md` and `HEARTBEAT.md` manually to simulate two heartbeats, verify tasks are consumed and notifications posted. Confirm cron jobs are scheduled.`
