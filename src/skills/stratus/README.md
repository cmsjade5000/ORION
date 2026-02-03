# STRATUS Skill

STRATUS manages infrastructure provisioning and CI/CD workflows for the Gateway system.

## Responsibilities

- **provisionResources(params: any): Promise<any>**  
  Entry point for provisioning or updating cloud infrastructure resources.
- **detectDrift(resources: any): Promise<any>**  
  Entry point for detecting configuration drift in provisioned resources.
