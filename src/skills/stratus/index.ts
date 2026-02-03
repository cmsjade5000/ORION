import util from 'util';
import child_process from 'child_process';

const execAsync = util.promisify(child_process.exec);

/**
 * Stub out a Docker-based test environment launch.
 */
export async function provisionResources(params: any): Promise<any> {
  const cmd = 'docker run --rm my-test-environment';
  console.log(`STRATUS: stub provisioning with command: ${cmd}`);
  return { cmd };
}

/**
 * Compare local openclaw.yaml against live gateway config and
 * return a list of mismatch lines (diff output).
 */
export async function detectDrift(resources: any): Promise<string[]> {
  try {
    // Use bash process substitution to diff files
    const diffCmd = 'bash -lc "diff -u openclaw.yaml <(openclaw gateway config.get)"';
    const { stdout } = await execAsync(diffCmd, { shell: '/bin/bash' });
    if (!stdout) {
      return [];
    }
    return stdout.split('\n');
  } catch (err: any) {
    const output = (err.stdout as string) || err.message || '';
    return output.split('\n');
  }
}
