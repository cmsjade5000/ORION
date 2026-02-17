import type { Bot } from "grammy";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

type Json = any;

function workspaceRoot(): string {
  const cands = [
    process.env.OPENCLAW_AGENT_WORKSPACE,
    process.env.OPENCLAW_WORKSPACE,
    process.env.ORION_WORKSPACE,
  ].filter(Boolean) as string[];
  if (cands.length) return path.resolve(cands[0]!);
  return process.cwd();
}

function fmtLocal(tsUnix: number): string {
  try {
    return new Date(tsUnix * 1000).toLocaleString();
  } catch {
    return String(tsUnix);
  }
}

function safeReadJson(p: string): Json | null {
  try {
    const raw = fs.readFileSync(p, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function listJsonFiles(dir: string): string[] {
  try {
    return fs
      .readdirSync(dir)
      .filter((n) => n.endsWith(".json"))
      .map((n) => path.join(dir, n));
  } catch {
    return [];
  }
}

function latestRunArtifact(root: string): { path: string; obj: any } | null {
  const runsDir = path.join(root, "tmp", "kalshi_ref_arb", "runs");
  const files = listJsonFiles(runsDir);
  if (!files.length) return null;
  // Artifacts are named <unix>.json
  files.sort((a, b) => {
    const ta = Number(path.basename(a, ".json")) || 0;
    const tb = Number(path.basename(b, ".json")) || 0;
    return ta - tb;
  });
  for (let i = files.length - 1; i >= 0; i--) {
    const p = files[i]!;
    const obj = safeReadJson(p);
    if (obj && typeof obj === "object") return { path: p, obj };
  }
  return null;
}

function killSwitchOn(root: string): boolean {
  return fs.existsSync(path.join(root, "tmp", "kalshi_ref_arb.KILL"));
}

function cooldownInfo(root: string): { active: boolean; remainingS: number; reason: string } {
  const p = path.join(root, "tmp", "kalshi_ref_arb", "cooldown.json");
  const obj = safeReadJson(p);
  if (!obj || typeof obj !== "object") return { active: false, remainingS: 0, reason: "" };
  const until = Number(obj.until_ts || 0);
  const now = Math.floor(Date.now() / 1000);
  const remaining = Math.max(0, until - now);
  return { active: remaining > 0, remainingS: remaining, reason: String(obj.reason || "") };
}

function extractCashAndPv(run: any): { cashUsd: number | null; pvUsd: number | null } {
  try {
    const postBal = run?.post?.balance;
    if (postBal && typeof postBal === "object") {
      const cash = Number(postBal.balance ?? postBal.cash ?? postBal.available ?? NaN);
      const pv = Number(postBal.portfolio_value ?? postBal.portfolioValue ?? NaN);
      return {
        cashUsd: Number.isFinite(cash) ? cash / 100.0 : null,
        pvUsd: Number.isFinite(pv) ? pv / 100.0 : null,
      };
    }
  } catch {}
  try {
    const bal = run?.balance?.balance;
    if (bal && typeof bal === "object") {
      const cash = Number(bal.balance ?? NaN);
      const pv = Number(bal.portfolio_value ?? NaN);
      return {
        cashUsd: Number.isFinite(cash) ? cash / 100.0 : null,
        pvUsd: Number.isFinite(pv) ? pv / 100.0 : null,
      };
    }
  } catch {}
  return { cashUsd: null, pvUsd: null };
}

function runDigest(root: string, hours: number): { ok: boolean; message: string } {
  const cmd = "python3";
  const args = ["scripts/kalshi_digest.py", "--window-hours", String(hours)];
  const proc = spawnSync(cmd, args, {
    cwd: root,
    encoding: "utf-8",
    timeout: 30_000,
    env: { ...process.env },
  });
  const stdout = String(proc.stdout || "").trim();
  if (proc.status === 0 && stdout) {
    try {
      const obj = JSON.parse(stdout);
      const msg = String(obj.message || "").trim();
      if (msg) return { ok: true, message: msg };
    } catch {
      // fall through
    }
  }
  const err = String(proc.stderr || "").trim();
  return { ok: false, message: err || "Digest generation failed." };
}

function readLatestDigest(root: string, maxAgeSeconds = 12 * 3600): string | null {
  const dir = path.join(root, "tmp", "kalshi_ref_arb", "digests");
  const files = listJsonFiles(dir);
  if (!files.length) return null;
  files.sort((a, b) => {
    const ta = Number(path.basename(a, ".json")) || 0;
    const tb = Number(path.basename(b, ".json")) || 0;
    return ta - tb;
  });
  const p = files[files.length - 1]!;
  const ts = Number(path.basename(p, ".json")) || 0;
  const now = Math.floor(Date.now() / 1000);
  if (ts && now - ts > maxAgeSeconds) return null;
  const obj = safeReadJson(p);
  const msg = String(obj?.message || "").trim();
  return msg || null;
}

function parseHoursArg(text: string): number | null {
  const parts = String(text || "").trim().split(/\s+/);
  if (parts.length < 2) return null;
  const n = Number(parts[1]);
  if (!Number.isFinite(n)) return null;
  if (n < 1 || n > 168) return null;
  return Math.floor(n);
}

export function registerKalshiCommands(bot: Bot) {
  bot.command("kalshi_status", async (ctx) => {
    const root = workspaceRoot();
    const last = latestRunArtifact(root);
    const kill = killSwitchOn(root);
    const cd = cooldownInfo(root);

    if (!last) {
      await ctx.reply("Kalshi status: no run artifacts found yet.");
      return;
    }

    const run = last.obj;
    const tsUnix = Number(run?.ts_unix || 0);
    const { cashUsd, pvUsd } = extractCashAndPv(run);
    const trade = run?.trade && typeof run.trade === "object" ? run.trade : {};
    const status = String(trade.status || "");
    const reason = String(trade.reason || "");
    const placed = Array.isArray(trade.placed) ? trade.placed : [];
    const livePlaced = placed.filter((p: any) => p && typeof p === "object" && p.mode === "live");

    const lines: string[] = [];
    lines.push("Kalshi status");
    if (tsUnix) lines.push(`Last cycle: ${fmtLocal(tsUnix)}`);
    lines.push(`Kill switch: ${kill ? "ON" : "OFF"}`);
    if (cd.active) lines.push(`Cooldown: ON (${Math.ceil(cd.remainingS / 60)}m) ${cd.reason ? `(${cd.reason})` : ""}`);
    else lines.push("Cooldown: OFF");
    if (cashUsd != null) lines.push(`Cash: $${cashUsd.toFixed(2)}`);
    if (pvUsd != null) lines.push(`Portfolio value: $${pvUsd.toFixed(2)}`);
    if (status) lines.push(`Trade: ${status}${reason ? ` (${reason})` : ""}`);

    if (livePlaced.length) {
      const o = livePlaced[0]?.order || {};
      lines.push(
        `Last order: ${o.action || "buy"} ${o.side || "?"} ${o.count || "?"}x ${o.ticker || "?"} @ ${o.price_dollars || "?"}`
      );
    } else {
      const diag = trade?.diagnostics;
      const bestPass = diag?.best_effective_edge_pass_filters;
      const bestBounds = diag?.best_effective_edge_in_bounds;
      const bestAny = diag?.best_effective_edge_any_quote ?? diag?.best_effective_edge;
      const best = bestPass ?? bestBounds ?? bestAny;
      if (best?.ticker) {
        try {
          const prefix = !bestPass && !bestBounds && bestAny ? "No trades (no quotes in bounds):" : "No trades:";
          lines.push(
            `${prefix} best eff edge ${Number(best.effective_edge_bps).toFixed(0)} bps on ${best.ticker} ${best.side} @ ${Number(best.ask).toFixed(4)}`
          );
        } catch {}
      }
      const totals = diag?.totals;
      if (totals && typeof totals === "object") {
        const qp = Number((totals as any).quotes_present ?? NaN);
        const pn = Number((totals as any).pass_non_edge_filters ?? NaN);
        if (Number.isFinite(qp) || Number.isFinite(pn)) {
          lines.push(`Diag: quotes ${Number.isFinite(qp) ? qp : "?"}, pass-non-edge ${Number.isFinite(pn) ? pn : "?"}`);
        }
      }
    }

    await ctx.reply(lines.filter(Boolean).join("\n"));
  });

  bot.command("kalshi_digest", async (ctx) => {
    const root = workspaceRoot();
    const hours = parseHoursArg(ctx.message?.text || "") ?? 8;

    // Prefer latest saved digest for speed; otherwise generate on-demand.
    const cached = readLatestDigest(root);
    if (cached && hours === 8) {
      await ctx.reply(cached);
      return;
    }

    const out = runDigest(root, hours);
    await ctx.reply(out.ok ? out.message : `Kalshi digest error: ${out.message}`);
  });
}
