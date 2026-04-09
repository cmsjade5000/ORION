import type { Bot } from "grammy";
import path from "node:path";
import { requireOperatorAccess } from "../access";
import { runCommand } from "../process";
import { BoundedExecutor, ChatTaskQueue } from "../queue";

type AssistantCmd =
  | "today"
  | "capture"
  | "followups"
  | "review"
  | "dreaming-status"
  | "dreaming-help"
  | "dreaming-on"
  | "dreaming-off";
type SlashAssistant = AssistantCmd;

const assistantExecutor = new BoundedExecutor(
  Number.parseInt(String(process.env.ORION_ASSISTANT_MAX_CONCURRENCY || "2"), 10) || 2
);
const assistantQueue = new ChatTaskQueue();

function workspaceRoot(): string {
  const candidates = [
    process.env.OPENCLAW_AGENT_WORKSPACE,
    process.env.OPENCLAW_WORKSPACE,
    process.env.ORION_WORKSPACE,
  ].filter(Boolean) as string[];
  if (candidates.length > 0) {
    return path.resolve(candidates[0]!);
  }
  return process.cwd();
}

function parseJsonMessage(raw: string): string | null {
  const lines = String(raw || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  for (let i = lines.length - 1; i >= 0; i -= 1) {
    try {
      const obj = JSON.parse(lines[i]!);
      const message = String(obj?.message || "").trim();
      if (message) return message;
    } catch {
      // Ignore non-JSON lines.
    }
  }
  return null;
}

async function runAssistantCommand(root: string, cmd: AssistantCmd, text?: string): Promise<{ ok: boolean; message: string }> {
  const argv =
    cmd === "capture"
      ? ["scripts/assistant_capture.py", "--text", text || "", "--json"]
      : ["scripts/assistant_status.py", "--cmd", cmd, "--json"];

  const proc = await runCommand("python3", argv, {
    cwd: root,
    timeoutMs: 45_000,
    env: { ...process.env },
  });

  const stdout = String(proc.stdout || "");
  const stderr = String(proc.stderr || "");
  const parsed = parseJsonMessage(stdout) || parseJsonMessage(stderr);

  if (proc.code === 0 && parsed) {
    return { ok: true, message: parsed };
  }
  if (proc.timedOut) {
    return { ok: false, message: "Assistant command timed out. Try again in a minute." };
  }
  return { ok: false, message: parsed || stderr.trim() || stdout.trim() || "Assistant command failed." };
}

export function parseAssistantSlashCommand(text: string): SlashAssistant | null {
  const trimmed = String(text || "").trim();
  if (!trimmed.startsWith("/")) return null;

  const tokens = trimmed.split(/\s+/);
  const token = tokens[0] || "";
  const base = token.toLowerCase().split("@")[0] || "";
  if (base === "/today") return "today";
  if (base === "/capture") return "capture";
  if (base === "/followups") return "followups";
  if (base === "/review") return "review";
  if (base === "/dreaming") {
    const action = String(tokens[1] || "status").toLowerCase();
    if (action === "on") return "dreaming-on";
    if (action === "off") return "dreaming-off";
    if (action === "help") return "dreaming-help";
    return "dreaming-status";
  }
  return null;
}

async function handleSlash(ctx: any, slash: SlashAssistant): Promise<void> {
  if (!(await requireOperatorAccess(ctx, "Assistant command"))) return;
  const root = workspaceRoot();
  const chatId = Number(ctx.chat?.id);
  const text = String(ctx.message?.text || "");

  const run = async () => {
    if (slash === "capture") {
      const captureText = text.replace(/^\/capture(?:@\S+)?/i, "").trim();
      if (!captureText) {
        await ctx.reply("Usage: /capture <text to save for POLARIS>");
        return;
      }
      const out = await assistantExecutor.run(() => runAssistantCommand(root, "capture", captureText));
      await ctx.reply(out.message);
      return;
    }

    const out = await assistantExecutor.run(() => runAssistantCommand(root, slash));
    await ctx.reply(out.message);
  };

  if (Number.isFinite(chatId)) {
    await assistantQueue.enqueue(chatId, run);
    return;
  }
  await run();
}

export function registerAssistantCommands(bot: Bot): void {
  bot.command("today", async (ctx) => {
    await handleSlash(ctx, "today");
  });

  bot.command("capture", async (ctx) => {
    await handleSlash(ctx, "capture");
  });

  bot.command("followups", async (ctx) => {
    await handleSlash(ctx, "followups");
  });

  bot.command("review", async (ctx) => {
    await handleSlash(ctx, "review");
  });

  bot.command("dreaming", async (ctx) => {
    const parsed = parseAssistantSlashCommand(String(ctx.message?.text || ""));
    await handleSlash(ctx, parsed && parsed.startsWith("dreaming-") ? parsed : "dreaming-status");
  });

  bot.on("message:text", async (ctx, next) => {
    const slash = parseAssistantSlashCommand(String(ctx.message?.text || ""));
    if (!slash) {
      await next();
      return;
    }
    await handleSlash(ctx, slash);
  });
}
