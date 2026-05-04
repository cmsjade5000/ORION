import { Bot, InlineKeyboard } from "grammy";
import { requireOperatorAccess } from "../access";
import { buildMiniAppUrl } from "../miniapp";

/**
 * Registers the /agents command to display the Agent Dashboard inline keyboard.
 */
export function registerDashboard(bot: Bot) {
  bot.command("agents", async (ctx) => {
    if (!(await requireOperatorAccess(ctx as never, "Agents dashboard"))) return;
    const keyboard = new InlineKeyboard()
      .text("ORION", "agent_ORION")
      .text("ATLAS", "agent_ATLAS")
      .row()
      .text("POLARIS", "agent_POLARIS")
      .text("WIRE", "agent_WIRE")
      .row()
      .text("SCRIBE", "agent_SCRIBE")
      .text("LEDGER", "agent_LEDGER")
      .row()
      .text("EMBER", "agent_EMBER")
      .row()
      .webApp("Open ORION", buildMiniAppUrl("home"));

    await ctx.reply("Select an agent to view details:", {
      reply_markup: keyboard,
    });
  });

  // Important UX: answer callback queries so Telegram doesn't leave the spinner stuck.
  bot.callbackQuery(/^agent_([A-Z]+)$/, async (ctx) => {
    if (!(await requireOperatorAccess(ctx as never, "Agents dashboard"))) {
      await ctx.answerCallbackQuery();
      return;
    }
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
    case "POLARIS":
      return [
        "POLARIS",
        "Admin co-pilot for reminders/calendar/email-prep/contact workflows (internal-only).",
      ].join("\n");
    case "WIRE":
      return [
        "WIRE",
        "Sources-first retrieval and release validation (internal-only).",
      ].join("\n");
    case "SCRIBE":
      return [
        "SCRIBE",
        "Send-ready drafting and formatting (internal-only).",
      ].join("\n");
    default:
      return null;
  }
}
