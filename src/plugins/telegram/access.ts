type CtxLike = {
  chat?: { id?: number | string; type?: string };
  from?: { id?: number | string };
  reply: (text: string) => Promise<unknown>;
};

function envBool(name: string, fallback: boolean): boolean {
  const raw = String(process.env[name] || "").trim().toLowerCase();
  if (!raw) return fallback;
  return ["1", "true", "yes", "on"].includes(raw);
}

function parseIds(raw: string): Set<string> {
  const ids = String(raw || "")
    .split(/[,\s]+/)
    .map((v) => v.trim())
    .filter(Boolean)
    .filter((v) => /^[0-9]+$/.test(v));
  return new Set(ids);
}

function configuredAllowedIds(): Set<string> {
  const merged = new Set<string>();
  const envs = [
    process.env.ORION_TELEGRAM_ALLOWED_USER_IDS,
    process.env.ORION_TELEGRAM_ADMIN_IDS,
    process.env.ORION_TELEGRAM_CHAT_ID,
    process.env.ORION_CORE_TELEGRAM_TARGET,
  ];
  for (const raw of envs) {
    const ids = parseIds(raw || "");
    for (const id of ids) merged.add(id);
  }
  return merged;
}

function toId(value: unknown): string {
  const raw = String(value ?? "").trim();
  return /^[0-9]+$/.test(raw) ? raw : "";
}

export async function requireOperatorAccess(ctx: CtxLike, commandLabel: string): Promise<boolean> {
  const allowed = configuredAllowedIds();
  const chatType = String(ctx.chat?.type || "");
  const fromId = toId(ctx.from?.id);
  const chatId = toId(ctx.chat?.id);

  if (allowed.size > 0) {
    if ((fromId && allowed.has(fromId)) || (chatId && allowed.has(chatId))) {
      return true;
    }
    await ctx.reply(`${commandLabel} is restricted. Configure allowlisted Telegram IDs for this bot.`);
    return false;
  }

  if (envBool("ORION_TELEGRAM_ALLOW_UNRESTRICTED_PRIVATE", false) && chatType === "private") {
    return true;
  }

  await ctx.reply(
    `${commandLabel} is disabled until operator IDs are configured (ORION_TELEGRAM_ALLOWED_USER_IDS or ORION_TELEGRAM_ADMIN_IDS).`
  );
  return false;
}
