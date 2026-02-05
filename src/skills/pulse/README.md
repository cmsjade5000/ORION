# PULSE Skill

PULSE is responsible for orchestrating data processing pipelines and handling retry logic for pipeline steps.

## Workflows

- **orchestratePipeline(params: any): Promise<any>**  
  Entry point for orchestrating heartbeat workflows defined in `workflows/heartbeat.yaml`. Executes jobs with retry/backoff and failure alerts as configured.

- **retryStep(stepId: string): Promise<any>**  
  (Deprecated) Legacy entry point for retrying a specific pipeline step. Dynamic workflows manage retries internally.

- **orchestrateDemo(): Promise<any>**  
  Entry point for running the agent-chat-demo workflow defined in `workflows/agent-chat-demo.yaml`. Checks `ENABLE_AGENT_CHAT_DEMO` environment variable or `pulse.enableAgentChatDemo` config flag; aborts if disabled. Sends handoff messages for each agent in sequence as configured.

## Demo Workflow Invocation

Run the agent chat demo workflow on demand:

```bash
openclaw sessions send --label pulse --message "demo:agent-chat-demo"
```

---
## Repo Mino Scan Workflow

Configure a list of Git repository URLs to scan nightly by setting `pulse.repoMinoScan.repos` in `openclaw.yaml`:

```yaml
pulse:
  repoMinoScan:
    repos:
      - https://github.com/vemetric/vemetric
      - https://github.com/AppFlowy/AppFlowy
      - https://github.com/taipy/taipy
      - https://github.com/nocodb/nocodb
      - https://github.com/kestra-io/kestra
      - https://github.com/composio-dev/composio
      - https://github.com/nocobase/nocobase
      - https://github.com/mattermost/mattermost-server
      - https://github.com/tooljet/tooljet
      - https://github.com/postiz/postiz
```

The `workflows/repo-mino-scan.yaml` runs nightly at **01:00 UTC**, invoking `scripts/scan_repos_with_mino.sh` to fetch each repo via Mino and compile a summary. On failure, PULSE will send an alert to Telegram:

```bash
# Trigger manual scan
openclaw sessions send --label pulse --message "demo:repo-mino-scan"
```


Run the agent chat demo workflow on demand:

```bash
openclaw sessions send --label pulse --message "demo:agent-chat-demo"
```

## Skill Repository Security Audit

Configure a list of skill repository URLs to audit nightly by setting `pulse.skillRepoAudit.repos` in `openclaw.yaml`:

```yaml
pulse:
  skillRepoAudit:
    repos:
      - https://github.com/your-org/skill-repo-1.git
      - https://github.com/your-org/skill-repo-2.git
```

The workflow `workflows/skill-repo-audit.yaml` runs daily at **02:30 UTC**, invoking the helper script `scripts/audit_skill_repos.sh`. This script clones or updates each repository and runs `openclaw security audit --deep`, producing a consolidated summary.

On failure, PULSE sends an alert to Telegram. You can also trigger the audit on demand:

```bash
openclaw sessions send --label pulse --message "skill-repo-audit"
```

## Dev Audit Pipeline

Configure cost thresholds and infrastructure drift settings in `openclaw.yaml` under `pulse.devAuditPipeline`:

```yaml
pulse:
  devAuditPipeline:
    stateDir: .state
    cost:
      warningThreshold: 100
      alertThreshold: 200
    drift:
      resources: {}
```

The workflow `workflows/dev-audit-pipeline.yaml` runs nightly at **03:30 UTC** and chains the following jobs in sequence:
1. Repo Mino Scan
2. Skill Repository Security Audit
3. LLM Cost Report
4. Infrastructure Drift Check

On failure of any step, PULSE sends an alert to Telegram. To trigger the pipeline on demand:

```bash
openclaw sessions send --label pulse --message "dev-audit-pipeline"
```

### Nightly Git Repo Sync

As the final step of the Dev Audit Pipeline, a `repo_sync` job runs `scripts/nightly_repo_sync.sh` to push any new commits on `HEAD` back to the `origin` remote:

```bash
# Manually trigger just the repo sync step
openclaw sessions send --label pulse --message "repo-sync"
```

