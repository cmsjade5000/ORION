import { describe, expect, it, vi } from "vitest";
import { Bot } from "grammy";
import { parseAssistantSlashCommand, registerAssistantCommands } from "./index";

describe("Assistant Telegram commands", () => {
  it("registers the assistant slash commands", () => {
    const bot = { command: vi.fn(), on: vi.fn() } as any as Bot;
    registerAssistantCommands(bot);

    expect(bot.command).toHaveBeenCalledWith("today", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("capture", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("followups", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("review", expect.any(Function));
    expect(bot.on).toHaveBeenCalledWith("message:text", expect.any(Function));
  });

  it("parses assistant slash commands with optional bot suffixes", () => {
    expect(parseAssistantSlashCommand("/today")).toBe("today");
    expect(parseAssistantSlashCommand("/capture@Orion_GatewayBot buy milk")).toBe("capture");
    expect(parseAssistantSlashCommand("/followups")).toBe("followups");
    expect(parseAssistantSlashCommand("/review")).toBe("review");
    expect(parseAssistantSlashCommand("today")).toBeNull();
  });
});
