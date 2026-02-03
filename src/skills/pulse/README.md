# PULSE Skill

PULSE is responsible for orchestrating data processing pipelines and handling retry logic for pipeline steps.

## Workflows

- **orchestratePipeline(params: any): Promise<any>**  
  Entry point for orchestrating a full data processing pipeline.
- **retryStep(stepId: string): Promise<any>**  
  Entry point for retrying a specific pipeline step.
