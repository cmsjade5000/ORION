import util from 'util';
import child_process from 'child_process';

const execAsync = util.promisify(child_process.exec);

interface Step {
  id: string;
  cmd: string;
}

const STEPS: Step[] = [
  { id: 'rotate_memory', cmd: 'python3 scripts/rotate_memory.py' },
  { id: 'heartbeat_summary', cmd: 'python3 scripts/heartbeat_summary.py' },
  { id: 'resurrect', cmd: 'bash scripts/resurrect.sh' },
  { id: 'nightly_review', cmd: 'python3 scripts/nightly_review.py' },
];

async function sendTelegramAlert(message: string): Promise<void> {
  try {
    await execAsync(`openclaw message send --text "${message}"`);
  } catch (err) {
    console.error('Failed to send Telegram alert:', err);
  }
}

/**
 * Orchestrate the Memory-Stack pipeline: rotate_memory, heartbeat_summary,
 * resurrect, nightly_review in sequence. Retries failed steps.
 */
export async function orchestratePipeline(params: any): Promise<any> {
  const results: Array<any> = [];
  for (const step of STEPS) {
    try {
      const { stdout } = await execAsync(step.cmd);
      results.push({ step: step.id, success: true, output: stdout });
    } catch (error) {
      const retryResult = await retryStep(step.id);
      if (retryResult.success) {
        results.push({ step: step.id, success: true, retried: true });
      } else {
        await sendTelegramAlert(
          `PULSE: step ${step.id} failed after ${retryResult.attempts} attempts`
        );
        results.push({ step: step.id, success: false, error: retryResult.error });
      }
    }
  }
  return results;
}

/**
 * Retry a failed pipeline step up to 2 times, then return failure.
 */
export async function retryStep(stepId: string): Promise<any> {
  const step = STEPS.find((s) => s.id === stepId);
  if (!step) {
    throw new Error(`Unknown step "${stepId}"`);
  }
  let attempts = 0;
  let lastError: any;
  while (attempts < 2) {
    attempts++;
    try {
      await execAsync(step.cmd);
      return { step: stepId, success: true, attempts };
    } catch (err) {
      lastError = err;
    }
  }
  return { step: stepId, success: false, attempts, error: lastError };
}
