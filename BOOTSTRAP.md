# BOOTSTRAP.md

This document records the bootstrapping process for adding the following specialist agents to the Gateway system:

- **EMBER** — Emotional Regulation & Grounding
- **ATLAS** — Execution & Operations
- **PIXEL** — Discovery, Tech, & Culture
- **NODE** — System Glue & Architecture
- **LEDGER** — Money, Value, & Financial Reasoning

## Steps Taken

1. **Defined role stubs** in `souls/roles/` for each agent, capturing core responsibilities, boundaries, and output preferences.
2. **Regenerated agent identities** using the Soul Factory, combining shared constitutional, foundational, and routing layers with each role definition:

   ```bash
   ./scripts/soul_factory.sh --all
   ```

3. **Verified** the generated `agents/<AGENT>/SOUL.md` files to ensure correctness and completeness.
4. **Committed** all changes to version control with an atomic commit covering role definitions, generated artifacts, and this bootstrap record.
