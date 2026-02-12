import type { Bot } from "grammy";

type FlowStep = "mood_genre" | "runtime" | "era" | "keyword";

type FlowState = {
  step: FlowStep;
  params: Record<string, string | number>;
  turn: number;
};

type ChatState = {
  flow?: FlowState;
  lastParams?: Record<string, string | number>;
  lastOffset?: number;
};

type DeepLinkResponse = {
  start_payload: Record<string, unknown>;
  start_param: string;
  deep_link: string;
  normalized_params: Record<string, string>;
};

const RAIL_STEPS: FlowStep[] = ["mood_genre", "runtime", "era", "keyword"];

const START_TRIGGERS = [
  "what should i watch",
  "recommend",
  "pick a movie",
  "movie night",
  "flic",
  "watch tonight",
];

const STOP_WORDS = new Set(["skip", "none", "no", "anything", "whatever", "surprise me"]);

const GENRE_ALIASES: Array<[string, string]> = [
  ["science fiction", "Sci-Fi"],
  ["sci fi", "Sci-Fi"],
  ["sci-fi", "Sci-Fi"],
  ["scifi", "Sci-Fi"],
  ["thriller", "Thriller"],
  ["horror", "Horror"],
  ["comedy", "Comedy"],
  ["drama", "Drama"],
  ["romance", "Romance"],
  ["romcom", "Romance"],
  ["rom-com", "Romance"],
  ["action", "Action"],
  ["crime", "Crime"],
  ["mystery", "Mystery"],
  ["fantasy", "Fantasy"],
  ["adventure", "Adventure"],
  ["family", "Family"],
  ["animation", "Animation"],
  ["animated", "Animation"],
  ["documentary", "Documentary"],
];

const MOOD_ALIASES: Array<[string, string]> = [
  ["heartfelt", "Heartfelt"],
  ["cozy", "Cozy"],
  ["funny", "Funny"],
  ["laugh", "Funny"],
  ["scary", "Scary"],
  ["intense", "Intense"],
  ["dark", "Dark"],
  ["moody", "Moody"],
  ["uplifting", "Uplifting"],
  ["romantic", "Romantic"],
  ["exciting", "Exciting"],
  ["cerebral", "Cerebral"],
];

export function __test_only_applyStepInput(
  flow: FlowState,
  text: string
): Record<string, string | number> {
  applyStepInput(flow, text);
  return flow.params;
}

export async function __test_only_buildDeepLink(
  params: Record<string, string | number>,
  opts?: { reroll?: boolean; offset?: number }
): Promise<DeepLinkResponse> {
  return buildDeepLink(params, opts);
}

function envBool(name: string, fallback: boolean): boolean {
  const raw = String(process.env[name] || "").trim().toLowerCase();
  if (!raw) return fallback;
  return ["1", "true", "yes", "on"].includes(raw);
}

function trimText(value: string, max = 120): string {
  return value.trim().replace(/\s+/g, " ").slice(0, max);
}

function choose(lines: string[], seed: number): string {
  if (!lines.length) return "";
  const index = Math.abs(seed) % lines.length;
  return lines[index];
}

function containsTrigger(text: string): boolean {
  const lower = text.toLowerCase();
  return START_TRIGGERS.some((t) => lower.includes(t));
}

function isSkippable(text: string): boolean {
  const lower = text.trim().toLowerCase();
  return STOP_WORDS.has(lower);
}

function dedupe(values: string[]): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const value of values) {
    if (!value || seen.has(value)) continue;
    seen.add(value);
    ordered.push(value);
  }
  return ordered;
}

function extractAliases(
  text: string,
  aliases: Array<[string, string]>,
  maxItems: number
): string[] {
  const lower = text.toLowerCase();
  const hits: string[] = [];
  for (const [needle, canonical] of aliases) {
    if (lower.includes(needle)) hits.push(canonical);
    if (hits.length >= maxItems) break;
  }
  return dedupe(hits);
}

function parseRuntime(text: string): number | undefined {
  const lower = text.toLowerCase();
  const hourMatch = lower.match(/(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours)/);
  if (hourMatch) {
    const hours = Number.parseFloat(hourMatch[1] || "0");
    if (Number.isFinite(hours) && hours > 0) {
      return Math.max(30, Math.round(hours * 60));
    }
  }

  const minMatch = lower.match(/(\d{2,3})\s*(m|min|mins|minute|minutes)?/);
  if (minMatch) {
    const mins = Number.parseInt(minMatch[1] || "0", 10);
    if (Number.isFinite(mins) && mins > 0) {
      return mins;
    }
  }

  if (lower.includes("short") || lower.includes("quick")) return 100;
  if (lower.includes("long") || lower.includes("epic")) return 165;
  return undefined;
}

function parseEra(text: string): { year_min?: number; year_max?: number } {
  const lower = text.toLowerCase();
  const range = lower.match(/(19\d{2}|20\d{2})\s*(?:-|to)\s*(19\d{2}|20\d{2})/);
  if (range) {
    const a = Number.parseInt(range[1] || "0", 10);
    const b = Number.parseInt(range[2] || "0", 10);
    if (a > 1800 && b > 1800) {
      return { year_min: Math.min(a, b), year_max: Math.max(a, b) };
    }
  }

  const decade = lower.match(/\b(19|20)(\d)0s\b/);
  if (decade) {
    const prefix = decade[1] || "";
    const digit = decade[2] || "";
    const start = Number.parseInt(`${prefix}${digit}0`, 10);
    return { year_min: start, year_max: start + 9 };
  }

  const single = lower.match(/\b(19\d{2}|20\d{2})\b/);
  if (single) {
    const year = Number.parseInt(single[1] || "0", 10);
    if (year > 1800) return { year_min: year - 3, year_max: year + 3 };
  }
  return {};
}

function nextStep(step: FlowStep): FlowStep | null {
  const idx = RAIL_STEPS.indexOf(step);
  if (idx < 0 || idx + 1 >= RAIL_STEPS.length) return null;
  return RAIL_STEPS[idx + 1] || null;
}

function getQuestion(step: FlowStep, seed: number): string {
  if (step === "mood_genre") {
    return `${choose(
      ["Director's cut opener:", "Riff mode:", "Dialing in the vibe:"],
      seed
    )} what mood and genre are we chasing tonight?`;
  }
  if (step === "runtime") {
    return `${choose(
      ["Runtime checkpoint:", "Pacing pass:", "Tempo lock:"],
      seed + 1
    )} how much time do you want to spend (minutes or hours)?`;
  }
  if (step === "era") {
    return `${choose(
      ["Time machine moment:", "Era filter:", "Decade dial:"],
      seed + 2
    )} any year range or decade?`;
  }
  return `${choose(
    ["Final polish:", "Last ingredient:", "One more tweak:"],
    seed + 3
  )} any keyword focus (actor/director/theme), or say "skip".`;
}

async function postJson(url: string, payload: Record<string, unknown>) {
  const globalFetch = (globalThis as any).fetch as
    | ((input: string, init?: any) => Promise<any>)
    | undefined;
  if (globalFetch) {
    return globalFetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  const nodeFetchModule = await import("node-fetch");
  const nodeFetch: any =
    (nodeFetchModule as any).default || (nodeFetchModule as any);
  return nodeFetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
}

async function buildDeepLink(
  params: Record<string, string | number>,
  opts?: { reroll?: boolean; offset?: number }
): Promise<DeepLinkResponse> {
  const base = String(process.env.FLIC_VAULT_BASE_URL || "https://vault966-r2.fly.dev").replace(
    /\/+$/,
    ""
  );
  const botUsername = String(process.env.FLIC_BOT_USERNAME || "Flic_GatewayBot");
  const appShortName = String(process.env.FLIC_APP_SHORT_NAME || "").trim();
  const response = await postJson(`${base}/api/webapp/deeplink/picks`, {
    params,
    reroll: Boolean(opts?.reroll),
    offset: opts?.offset,
    bot_username: botUsername,
    app_short_name: appShortName || undefined,
  });
  if (!response?.ok) {
    const body = await response?.text?.();
    throw new Error(`Deep link build failed (${response?.status}): ${body || "unknown"}`);
  }
  return (await response.json()) as DeepLinkResponse;
}

function applyStepInput(flow: FlowState, text: string): void {
  if (flow.step === "mood_genre") {
    const genres = extractAliases(text, GENRE_ALIASES, 3);
    const moods = extractAliases(text, MOOD_ALIASES, 3);
    if (genres.length) flow.params.genres = genres.join(",");
    if (moods.length) flow.params.moods = moods.join(",");
    if (!genres.length && !moods.length && !isSkippable(text)) {
      flow.params.q = trimText(text, 120);
    }
    return;
  }
  if (flow.step === "runtime") {
    const runtimeMax = parseRuntime(text);
    if (runtimeMax) flow.params.runtime_max = runtimeMax;
    return;
  }
  if (flow.step === "era") {
    const era = parseEra(text);
    if (era.year_min) flow.params.year_min = era.year_min;
    if (era.year_max) flow.params.year_max = era.year_max;
    return;
  }
  if (!isSkippable(text)) {
    flow.params.q = trimText(text, 120);
  }
}

function shouldHandleMessage(text: string): boolean {
  if (!text) return false;
  const trimmed = text.trim();
  if (!trimmed) return false;
  return true;
}

function parseSlashCommand(text: string): "flic" | "reroll" | "flicreset" | null {
  const trimmed = text.trim();
  if (!trimmed.startsWith("/")) return null;
  const token = trimmed.split(/\s+/)[0] || "";
  const base = token.toLowerCase().split("@")[0] || "";
  if (base === "/flic") return "flic";
  if (base === "/reroll") return "reroll";
  if (base === "/flicreset") return "flicreset";
  return null;
}

export function registerFlicChatRouter(bot: Bot) {
  if (!envBool("FLIC_ROUTER_ENABLED", true)) return;

  const states = new Map<number, ChatState>();

  const beginFlow = async (ctx: any, chatId: number) => {
    const state = states.get(chatId) || {};
    state.flow = { step: "mood_genre", params: {}, turn: 0 };
    states.set(chatId, state);
    await ctx.reply(
      "Flic on rails, but with banter. I’ll ask four quick questions and end with a locked Picks link."
    );
    await ctx.reply(getQuestion("mood_genre", chatId));
  };

  const resetFlow = async (ctx: any, chatId: number) => {
    states.delete(chatId);
    await ctx.reply("Flow reset. Send /flic when you want a fresh recommendation run.");
  };

  const rerollFlow = async (ctx: any, chatId: number) => {
    const state = states.get(chatId);
    if (!state?.lastParams) {
      await ctx.reply('No previous picks context yet. Start with /flic and I will set one up.');
      return;
    }
    try {
      const reroll = await buildDeepLink(state.lastParams, {
        reroll: true,
        offset: state.lastOffset || 0,
      });
      const nextOffset = Number.parseInt(reroll.normalized_params?.offset || "0", 10) || 0;
      state.lastOffset = nextOffset;
      states.set(chatId, state);
      await ctx.reply(
        [
          "Reroll cut is ready. Same vibe, fresh stack.",
          `Offset: ${nextOffset}`,
          reroll.deep_link,
        ].join("\n")
      );
    } catch {
      await ctx.reply("I couldn't build a reroll link just now. Try again in a moment.");
    }
  };

  bot.command("flic", async (ctx) => {
    const chatId = Number(ctx.chat?.id);
    if (!Number.isFinite(chatId)) return;
    if (ctx.chat?.type !== "private") {
      await ctx.reply("Flic picks are DM-only right now. Message me directly and I’ll set up a watch plan.");
      return;
    }
    await beginFlow(ctx, chatId);
  });

  bot.command("flicreset", async (ctx) => {
    const chatId = Number(ctx.chat?.id);
    if (!Number.isFinite(chatId)) return;
    await resetFlow(ctx, chatId);
  });

  bot.command("reroll", async (ctx) => {
    const chatId = Number(ctx.chat?.id);
    if (!Number.isFinite(chatId)) return;
    await rerollFlow(ctx, chatId);
  });

  bot.on("message:text", async (ctx, next) => {
    if (ctx.chat?.type !== "private") return;
    const text = String(ctx.message?.text || "");
    if (!shouldHandleMessage(text)) return;

    const chatId = Number(ctx.chat?.id);
    if (!Number.isFinite(chatId)) return;
    const slash = parseSlashCommand(text);
    if (slash === "flic") {
      await beginFlow(ctx, chatId);
      return;
    }
    if (slash === "flicreset") {
      await resetFlow(ctx, chatId);
      return;
    }
    if (slash === "reroll") {
      await rerollFlow(ctx, chatId);
      return;
    }

    const state = states.get(chatId) || {};

    if (!state.flow) {
      if (!containsTrigger(text)) {
        await next();
        return;
      }
      state.flow = { step: "mood_genre", params: {}, turn: 0 };
      states.set(chatId, state);
      await ctx.reply(
        "Let's build tonight's cut. Four quick prompts, then I’ll drop a locked Picks link."
      );
      await ctx.reply(getQuestion("mood_genre", chatId));
      return;
    }

    const flow = state.flow;
    flow.turn += 1;
    applyStepInput(flow, text);
    const upcoming = nextStep(flow.step);
    if (upcoming) {
      flow.step = upcoming;
      states.set(chatId, state);
      await ctx.reply(getQuestion(upcoming, chatId + flow.turn));
      return;
    }

    try {
      const deep = await buildDeepLink(flow.params);
      const normalized = deep.normalized_params || {};
      state.lastParams = { ...flow.params };
      state.lastOffset = Number.parseInt(normalized.offset || "0", 10) || 0;
      state.flow = undefined;
      states.set(chatId, state);

      const planBits: string[] = [];
      if (normalized.genres) planBits.push(`Genres ${normalized.genres}`);
      if (normalized.moods) planBits.push(`Moods ${normalized.moods}`);
      if (normalized.runtime_max) planBits.push(`Runtime ≤ ${normalized.runtime_max}m`);
      if (normalized.year_min || normalized.year_max) {
        planBits.push(`Years ${normalized.year_min || "Any"}-${normalized.year_max || "Now"}`);
      }

      await ctx.reply(
        [
          choose(
            [
              "Director's cut plan locked.",
              "This slate should hit your lane clean.",
              "Riff complete. Picks are queued.",
            ],
            chatId + flow.turn
          ),
          planBits.length ? `Plan: ${planBits.join(" | ")}` : "Plan: smart default mix.",
          deep.deep_link,
          'If you want another stack with the same filters, send /reroll.',
        ].join("\n")
      );
    } catch {
      state.flow = undefined;
      states.set(chatId, state);
      await ctx.reply(
        "I hit a routing snag while generating the mini-app link. Send /flic and I’ll re-run the flow."
      );
    }
  });
}
