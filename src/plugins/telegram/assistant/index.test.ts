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
    expect(bot.command).toHaveBeenCalledWith("dreaming", expect.any(Function));
    expect(bot.on).toHaveBeenCalledWith("message:text", expect.any(Function));
  });

  it("parses assistant slash commands with optional bot suffixes", () => {
    expect(parseAssistantSlashCommand("/today")).toBe("today");
    expect(parseAssistantSlashCommand("/capture@Orion_GatewayBot buy milk")).toBe("capture");
    expect(parseAssistantSlashCommand("/followups")).toBe("followups");
    expect(parseAssistantSlashCommand("/review")).toBe("review");
    expect(parseAssistantSlashCommand("/dreaming")).toBe("dreaming-status");
    expect(parseAssistantSlashCommand("/dreaming status")).toBe("dreaming-status");
    expect(parseAssistantSlashCommand("/dreaming on")).toBe("dreaming-on");
    expect(parseAssistantSlashCommand("/dreaming off")).toBe("dreaming-off");
    expect(parseAssistantSlashCommand("/dreaming help")).toBe("dreaming-help");
    expect(parseAssistantSlashCommand("/dreaming nonsense")).toBe("dreaming-status");
    expect(parseAssistantSlashCommand("today")).toBeNull();
  });
});
