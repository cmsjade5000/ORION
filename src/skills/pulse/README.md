# PULSE Skill

PULSE is responsible for orchestrating data processing pipelines and handling retry logic for pipeline steps.

## Workflows

- **orchestratePipeline(params: any): Promise<any>**  
  Entry point for orchestrating heartbeat workflows defined in `workflows/heartbeat.yaml`. Executes jobs with retry/backoff and failure alerts as configured.

- **retryStep(stepId: string): Promise<any>**  
  (Deprecated) Legacy entry point for retrying a specific pipeline step. Dynamic workflows manage retries internally.
