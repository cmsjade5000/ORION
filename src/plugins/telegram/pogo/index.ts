import type { Bot } from "grammy";
import { spawnSync } from "node:child_process";
import path from "node:path";

type PogoCmd = "help" | "voice" | "text" | "today" | "status";

type SlashPogo = "pogo_help" | "pogo_voice" | "pogo_text" | "pogo_today" | "pogo_status";

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

function mapSlashToCmd(slash: SlashPogo): PogoCmd {
  switch (slash) {
    case "pogo_help":
      return "help";
    case "pogo_voice":
      return "voice";
    case "pogo_text":
      return "text";
    case "pogo_today":
      return "today";
    case "pogo_status":
      return "status";
  }
}

function parseJsonMessage(raw: string): string | null {
  const lines = String(raw || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  for (let i = lines.length - 1; i >= 0; i--) {
    try {
      const obj = JSON.parse(lines[i]!);
      const message = String(obj?.message || "").trim();
      if (message) return message;
    } catch {
      // Keep scanning lines from bottom.
    }
  }

  return null;
}

function runPogoCommand(root: string, cmd: PogoCmd): { ok: boolean; message: string } {
  const proc = spawnSync("python3", ["scripts/pogo_brief_commands.py", "--cmd", cmd], {
    cwd: root,
    encoding: "utf-8",
    timeout: 180_000,
    env: { ...process.env },
  });

  const stdout = String(proc.stdout || "");
  const stderr = String(proc.stderr || "");
  const parsed = parseJsonMessage(stdout) || parseJsonMessage(stderr);

  if (proc.status === 0 && parsed) {
    return { ok: true, message: parsed };
  }

  const fallback = parsed || stderr.trim() || stdout.trim() || "Pokemon GO command failed.";
  return { ok: false, message: fallback };
}

export function parsePogoSlashCommand(text: string): SlashPogo | null {
  const trimmed = String(text || "").trim();
  if (!trimmed.startsWith("/")) return null;

  const token = trimmed.split(/\s+/)[0] || "";
  const base = token.toLowerCase().split("@")[0] || "";

  if (base === "/pogo_help") return "pogo_help";
  if (base === "/pogo_voice") return "pogo_voice";
  if (base === "/pogo_text") return "pogo_text";
  if (base === "/pogo_today") return "pogo_today";
  if (base === "/pogo_status") return "pogo_status";

  return null;
}

async function handleSlash(ctx: any, slash: SlashPogo): Promise<void> {
  const root = workspaceRoot();
  const cmd = mapSlashToCmd(slash);
  const out = runPogoCommand(root, cmd);
  await ctx.reply(out.message);
}

export function registerPogoCommands(bot: Bot): void {
  bot.command("pogo_help", async (ctx) => {
    await handleSlash(ctx, "pogo_help");
  });

  bot.command("pogo_voice", async (ctx) => {
    await handleSlash(ctx, "pogo_voice");
  });

  bot.command("pogo_text", async (ctx) => {
    await handleSlash(ctx, "pogo_text");
  });

  bot.command("pogo_today", async (ctx) => {
    await handleSlash(ctx, "pogo_today");
  });

  bot.command("pogo_status", async (ctx) => {
    await handleSlash(ctx, "pogo_status");
  });

  // Plain-text fallback for runtimes where native Telegram command routing is inconsistent.
  bot.on("message:text", async (ctx, next) => {
    const slash = parsePogoSlashCommand(String(ctx.message?.text || ""));
    if (!slash) {
      await next();
      return;
    }

    await handleSlash(ctx, slash);
  });
}
