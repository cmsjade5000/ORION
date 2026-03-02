import { Bot } from "grammy";
import { parsePogoSlashCommand, registerPogoCommands } from "./index";

describe("Pogo command registration", () => {
  it("registers all /pogo_* command handlers", () => {
    const bot = { command: jest.fn(), on: jest.fn() } as any as Bot;
    registerPogoCommands(bot);

    expect(bot.command).toHaveBeenCalledWith("pogo_help", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("pogo_voice", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("pogo_text", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("pogo_today", expect.any(Function));
    expect(bot.command).toHaveBeenCalledWith("pogo_status", expect.any(Function));
    expect(bot.on).toHaveBeenCalledWith("message:text", expect.any(Function));
  });
});

describe("parsePogoSlashCommand", () => {
  it("matches direct slash commands", () => {
    expect(parsePogoSlashCommand("/pogo_text")).toBe("pogo_text");
    expect(parsePogoSlashCommand("/pogo_voice")).toBe("pogo_voice");
  });

  it("matches slash commands with bot suffix", () => {
    expect(parsePogoSlashCommand("/pogo_text@ORION")).toBe("pogo_text");
    expect(parsePogoSlashCommand("/pogo_status@orion_bot some extra")).toBe("pogo_status");
  });

  it("returns null for non-pogo messages", () => {
    expect(parsePogoSlashCommand("pogo_text")).toBeNull();
    expect(parsePogoSlashCommand("/paper_status")).toBeNull();
  });
});
