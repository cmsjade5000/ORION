# Memory Backends

The Gateway system supports multiple memory backends for storing and retrieving contextual memory entries.

**Current setup uses the local `memory/` folder only.**

Per current project direction: **ignore QMD for now** (no docs/work required in this phase).

---

## Default Memory Backend

By default, Gateway uses the `memory/` folder (session dumps and daily memory files) as its working long‑term memory store. Daily summaries and session dumps are combined into `memory/YYYY-MM-DD.md` files, which are automatically searched when agents perform memory lookups.

<small>See [README.md](../README.md) for a high-level overview of memory configuration and other system settings.</small>
