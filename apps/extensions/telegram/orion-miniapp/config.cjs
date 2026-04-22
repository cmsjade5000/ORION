const path = require("node:path");
const fs = require("node:fs");
const os = require("node:os");

function parseIds(raw) {
  return String(raw || "")
    .split(/[,\s]+/)
    .map((value) => value.trim())
    .filter(Boolean)
    .filter((value) => /^[0-9]+$/.test(value));
}

function unique(values) {
  return [...new Set(values)];
}

function readOpenClawTelegramIds() {
  const configPath = path.join(os.homedir(), ".openclaw", "openclaw.json");
  try {
    const payload = JSON.parse(fs.readFileSync(configPath, "utf8"));
    const telegram = ((payload || {}).channels || {}).telegram || {};
    return unique([
      ...parseIds((telegram.allowFrom || []).join(",")),
      ...parseIds((((telegram.dm || {}).allowFrom) || []).join(",")),
    ]);
  } catch {
    return [];
  }
}

function workspaceRoot() {
  const candidates = [
    process.env.ORION_WORKSPACE,
    process.env.OPENCLAW_AGENT_WORKSPACE,
    process.env.OPENCLAW_WORKSPACE,
    process.cwd(),
  ].filter(Boolean);
  return path.resolve(candidates[0]);
}

function configuredOperatorIds() {
  return unique(
    [
      ...parseIds(process.env.ORION_MINIAPP_OPERATOR_IDS),
      ...parseIds(process.env.ORION_TELEGRAM_ALLOWED_USER_IDS),
      ...parseIds(process.env.ORION_TELEGRAM_ADMIN_IDS),
      ...parseIds(process.env.ORION_TELEGRAM_CHAT_ID),
      ...parseIds(process.env.ORION_TELEGRAM_TARGET),
      ...parseIds(process.env.ORION_CORE_TELEGRAM_TARGET),
      ...readOpenClawTelegramIds(),
    ].filter(Boolean)
  );
}

function normalizeBaseUrl(raw) {
  const value = String(raw || "https://mac-mini.tail5e899c.ts.net").trim();
  return value.replace(/\/+$/, "");
}

function buildMiniAppUrl(baseUrl, startapp) {
  const url = new URL(normalizeBaseUrl(baseUrl));
  if (startapp) {
    url.searchParams.set("startapp", startapp);
  }
  return url.toString();
}

function publicConfig() {
  const baseUrl = normalizeBaseUrl(process.env.ORION_MINIAPP_URL);
  const tokenFile = process.env.ORION_TELEGRAM_BOT_TOKEN_FILE || path.join(os.homedir(), ".openclaw", "secrets", "telegram.token");
  const tokenFromFile = (() => {
    try {
      return fs.readFileSync(tokenFile, "utf8").trim();
    } catch {
      return "";
    }
  })();
  return {
    appName: process.env.ORION_MINIAPP_NAME || "ORION",
    baseUrl,
    host: process.env.ORION_MINIAPP_HOST || "0.0.0.0",
    port: Number.parseInt(process.env.PORT || process.env.ORION_MINIAPP_PORT || "8787", 10) || 8787,
    workspaceRoot: workspaceRoot(),
    operatorIds: configuredOperatorIds(),
    botToken:
      process.env.ORION_TELEGRAM_BOT_TOKEN ||
      process.env.TELEGRAM_BOT_TOKEN ||
      process.env.OPENCLAW_TELEGRAM_BOT_TOKEN ||
      tokenFromFile,
    allowedClockSkewSeconds:
      Number.parseInt(process.env.ORION_MINIAPP_MAX_INIT_AGE_SECONDS || "43200", 10) || 43200,
  };
}

module.exports = {
  buildMiniAppUrl,
  configuredOperatorIds,
  normalizeBaseUrl,
  parseIds,
  publicConfig,
  readOpenClawTelegramIds,
  workspaceRoot,
};
