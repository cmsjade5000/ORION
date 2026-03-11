import { spawn } from "node:child_process";

export type CommandRunResult = {
  code: number | null;
  stdout: string;
  stderr: string;
  signal: NodeJS.Signals | null;
  timedOut: boolean;
};

type RunCommandOptions = {
  cwd: string;
  env?: NodeJS.ProcessEnv;
  timeoutMs: number;
};

export async function runCommand(
  command: string,
  argv: string[],
  options: RunCommandOptions
): Promise<CommandRunResult> {
  return new Promise<CommandRunResult>((resolve) => {
    const child = spawn(command, argv, {
      cwd: options.cwd,
      env: options.env,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    let settled = false;
    let timedOut = false;

    const timeoutMs = Math.max(1, Math.trunc(options.timeoutMs));
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGTERM");
      const hardKill = setTimeout(() => child.kill("SIGKILL"), 2_000);
      hardKill.unref();
    }, timeoutMs);

    child.stdout?.on("data", (chunk) => {
      stdout += String(chunk);
    });
    child.stderr?.on("data", (chunk) => {
      stderr += String(chunk);
    });

    child.once("error", (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({
        code: 1,
        stdout,
        stderr: [stderr, error.message].filter(Boolean).join("\n"),
        signal: null,
        timedOut,
      });
    });

    child.once("close", (code, signal) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({
        code: typeof code === "number" ? code : null,
        stdout,
        stderr,
        signal,
        timedOut,
      });
    });
  });
}
