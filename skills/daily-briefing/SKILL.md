---
name: daily-briefing
description: Chief-of-staff style morning and evening briefing workflow for ORION with explicit assumptions and no invented facts.
metadata:
  invocation: user
---

# Daily Briefing

Use this skill when Cory asks for a morning plan, daily briefing, day reset, or evening closeout.

## Trigger Phrases / When To Use

- "Give me my daily briefing."
- "Plan my morning."
- "What should I focus on today?"
- "Evening reset."
- "Help me shut down and prep tomorrow."

## Inputs To Gather

Collect these before drafting:

- Tasks: priority list, carry-overs, blocked items.
- Calendar: meetings and fixed commitments for today.
- Deadlines: due today, due tomorrow, and high-risk this week.
- Weather: practical impact (commute, workout, travel).
- Energy: user self-rating (1-5) plus any constraints (sleep, stress, bandwidth).

Minimum required for a full brief:

- Tasks
- Calendar
- Deadlines
- Energy

Weather is optional but preferred.

## Workflow (With Stop Gates)

1. Confirm brief type: `morning` or `evening`.
2. Gather inputs from available sources.
3. If any required input is missing, run a short intake:
   - "Top 3 tasks?"
   - "Any fixed meetings today?"
   - "What is due today or tomorrow?"
   - "Energy 1-5?"
4. Stop gate: if 2 or more required inputs remain missing after intake, do not fabricate.
   - Return a minimal "partial brief" and explicitly list missing fields.
5. Build priorities:
   - Choose 1 main objective, 2 secondary objectives, and 1 fallback task.
   - Align timing with calendar constraints and current energy.
6. Add risk checks:
   - Deadline collision
   - Context switching overload
   - Low-energy periods
7. Produce final brief using the templates below.
8. If user asks to schedule reminders or recurring actions, delegate to ATLAS with a Task Packet. Do not claim scheduling is configured until executed and verified.

## Output Template: Morning Brief

```text
MORNING BRIEF - <Day, YYYY-MM-DD> (<Timezone>)

Mission:
- <single sentence objective for today>

Top Outcomes:
1. <Outcome 1>
2. <Outcome 2>
3. <Outcome 3>

Schedule Reality Check:
- Fixed: <meetings/appointments with time>
- Open windows: <time blocks available for deep work>
- Risk: <collision or bottleneck>

Deadlines:
- Today: <items>
- Tomorrow: <items>
- This week (high risk): <items>

Weather / Logistics:
- <impact summary or "Not available">

Energy Plan:
- Current energy: <1-5>
- Best work block: <time>
- Low-energy fallback: <small useful task>

First Action (next 15 minutes):
- <single concrete step>

Assumptions / Unknowns:
- [Assumption] <only if needed>
- Missing: <fields not provided>
```

## Output Template: Evening Reset (Optional)

```text
EVENING RESET - <Day, YYYY-MM-DD> (<Timezone>)

What Got Done:
- <wins, shipped work, completed commitments>

Carry Forward:
- <unfinished items moved to tomorrow with reason>

Deadline Check:
- <new urgency or unchanged status>

Tomorrow Setup:
1. <top priority for tomorrow>
2. <secondary priority>
3. <support task>

Calendar Prep:
- First fixed event: <time/event>
- Required prep tonight: <yes/no + item>

Shutdown Step (next 10 minutes):
- <single cleanup action>

Assumptions / Unknowns:
- [Assumption] <only if needed>
- Missing: <fields not provided>
```

## Constraints

- Do not invent tasks, meetings, deadlines, weather, or completion status.
- Mark every inference as `[Assumption]`.
- Keep it concise and actionable.
- Prefer concrete time blocks and next actions over general advice.
- If data is stale or uncertain, say so explicitly.
