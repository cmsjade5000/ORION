# Memory Backends

The Gateway system supports multiple memory backends for storing and retrieving contextual memory entries. Memory backends allow you to mix and match long‑term memory in daily summaries alongside external knowledge sources such as a Quick Markdown (QMD) workspace for your personal notes.

---

## Default Memory Backend

By default, Gateway uses the `memory/` folder (session dumps and daily memory files) as its working long‑term memory store. Daily summaries and session dumps are combined into `memory/YYYY-MM-DD.md` files, which are automatically searched when agents perform memory lookups.

## QMD Workspace Backend

The QMD backend integrates with [qmd-skill (Quick Markdown Search)](https://github.com/openclaw/skills/tree/main/skills/lifecoacher/qmd-skill-2) to index and search a local folder of Markdown notes (e.g. your second brain or project docs). This backend is **opt‑in** and must be enabled in `openclaw.yaml`.

### Configuration

Add a `memory.backends.qmd` section to your `openclaw.yaml`:

```yaml
memory:
  backends:
    qmd:
      enabled: true          # set to 'true' to turn on QMD integration
      path: ./path/to/notes  # relative or absolute path to your Markdown workspace
```

- `enabled` (boolean): Whether to include the QMD workspace in memory searches.
- `path` (string): Filesystem path to the root of your Markdown note collection. All `.md` files in this folder will be indexed and searched.

After enabling, restart the gateway service to pick up the new configuration.

### Requirements

- **qmd** CLI must be installed and on your `$PATH`. For installation instructions, see the [qmd-skill documentation](https://github.com/openclaw/skills/tree/main/skills/lifecoacher/qmd-skill-2).

### Search Behavior

1. When enabled, Gateway will invoke the QMD CLI to build or refresh the index of your Markdown workspace.
2. A QMD query is issued for each memory lookup, returning a list of matching notes with relevance scores and excerpts.
3. If the `qmd` binary is not found in your environment, Gateway will automatically fall back to a simple substring search across `.md` files in the specified workspace.
4. QMD results are injected **before** the default daily memory entries from `memory/`.

### Retrieving Note Content

Agents can retrieve the full content of any QMD search result via its URI (relative path under your workspace), enabling deeper context or follow‑up queries against a specific document.

---

<small>See [README.md](../README.md) for a high-level overview of memory configuration and other system settings.</small>
