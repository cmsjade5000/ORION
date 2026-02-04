import fs from 'fs';
import path from 'path';
import util from 'util';
import child_process from 'child_process';
import yaml from 'js-yaml';

const execAsync = util.promisify(child_process.exec);

async function sendTelegramAlert(channel: string, target: string, message: string): Promise<void> {
  try {
    await execAsync(
      `openclaw message send --channel ${channel} --target ${target} --text "${message}"`
    );
  } catch (err) {
    console.error('Failed to send Telegram alert:', err);
  }
}

function parseDuration(duration: string): number {
  const match = duration.match(/^(\d+)([smhd])$/);
  if (!match) {
    return 0;
  }
  const value = parseInt(match[1], 10);
  const unit = match[2];
  switch (unit) {
    case 's':
      return value * 1000;
    case 'm':
      return value * 60 * 1000;
    case 'h':
      return value * 60 * 60 * 1000;
    case 'd':
      return value * 24 * 60 * 60 * 1000;
    default:
      return 0;
  }
}

/**
 * Orchestrate heartbeat jobs as defined in workflows/heartbeat.yaml.
 * Loads job definitions, executes commands with retry/backoff, and handles failure alerts.
 */
export async function orchestratePipeline(params: any): Promise<any> {
  const workflowPath = path.resolve(__dirname, '../../../workflows/heartbeat.yaml');
  const content = fs.readFileSync(workflowPath, 'utf8');
  const workflow = yaml.load(content) as any;
  const results: any[] = [];

  for (const [jobId, jobDef] of Object.entries(workflow.jobs || {})) {
    const cmd = (jobDef as any).command as string;
    const retryPolicy = (jobDef as any).retry || {};
    const maxAttempts = (retryPolicy as any).max_attempts || 1;
    const backoff = (retryPolicy as any).backoff || {};
    const initialDelayMs = parseDuration((backoff as any).initial_delay || '');
    const factor = (backoff as any).factor || 1;

    let attempt = 0;
    let success = false;
    let lastError: any;
    let delayMs = initialDelayMs;

    while (attempt < maxAttempts) {
      attempt++;
      try {
        const { stdout } = await execAsync(cmd);
        results.push({ job: jobId, success: true, output: stdout, attempts: attempt });
        success = true;
        break;
      } catch (err: any) {
        lastError = err;
        if (attempt < maxAttempts) {
          await new Promise((r) => setTimeout(r, delayMs));
          delayMs *= factor;
        }
      }
    }

    if (!success) {
      for (const hook of ((jobDef as any).on_failure || [])) {
        if ((hook as any).message) {
          const msgHook = (hook as any).message;
          const msg = (msgHook.message as string).replace(
            /{{\s*attempts\s*}}/g,
            String(attempt)
          );
          await sendTelegramAlert(msgHook.channel, msgHook.target, msg);
        }
      }
      results.push({ job: jobId, success: false, error: lastError, attempts: attempt });
    }
  }

  return results;
}

/**
 * Retry entrypoint retained for compatibility. Dynamic workflows handle retry internally.
 */
export async function retryStep(stepId: string): Promise<any> {
  throw new Error('retryStep is not supported in dynamic workflow mode');
}
