import { Bot, InlineKeyboard } from "grammy";

/**
 * Registers the /agents command to display the Agent Dashboard inline keyboard.
 */
export function registerDashboard(bot: Bot) {
  bot.command("agents", async (ctx) => {
    const keyboard = new InlineKeyboard()
      .text("ORION", "agent_ORION")
      .text("EMBER", "agent_EMBER")
      .row()
      .text("ATLAS", "agent_ATLAS")
      .text("PIXEL", "agent_PIXEL")
      .row()
      .text("NODE", "agent_NODE")
      .text("LEDGER", "agent_LEDGER");

    await ctx.reply("Select an agent to view details:", {
      reply_markup: keyboard,
    });
  });

  // Important UX: answer callback queries so Telegram doesn't leave the spinner stuck.
  bot.callbackQuery(/^agent_([A-Z]+)$/, async (ctx) => {
    const agentId = String(ctx.match?.[1] || "").trim();
    const info = agentInfo(agentId);
    await ctx.answerCallbackQuery();
    await ctx.reply(info ?? `Unknown agent: ${agentId}`);
  });
}

function agentInfo(id: string): string | null {
  switch (id) {
    case "ORION":
      return [
        "ORION",
        "User-facing ingress. Send it a message to delegate work to specialists.",
      ].join("\n");
    case "ATLAS":
      return [
        "ATLAS",
        "Ops/execution director (coordinates NODE/PULSE/STRATUS for infra work).",
      ].join("\n");
    case "NODE":
      return [
        "NODE",
        "System glue and coordination (internal-only).",
      ].join("\n");
    case "PULSE":
      return [
        "PULSE",
        "Scheduling and workflow automation (internal-only).",
      ].join("\n");
    case "STRATUS":
      return [
        "STRATUS",
        "DevOps and gateway implementation (internal-only).",
      ].join("\n");
    case "PIXEL":
      return [
        "PIXEL",
        "Discovery and inspiration (internal-only).",
      ].join("\n");
    case "EMBER":
      return [
        "EMBER",
        "Emotional support and tone calibration (internal-only).",
      ].join("\n");
    case "LEDGER":
      return [
        "LEDGER",
        "Cost/value tradeoffs (internal-only).",
      ].join("\n");
    default:
      return null;
  }
}
