import { createHmac, timingSafeEqual } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const TELEGRAM_INIT_DATA_HEADER = "x-telegram-init-data";
const MAX_TELEGRAM_INIT_DATA_LENGTH = 8_192;

type MutationAuthStatus = 401 | 403 | 503;

export interface MutationAuthFailure {
  ok: false;
  status: MutationAuthStatus;
  code: "UNAUTHORIZED" | "FORBIDDEN" | "MISCONFIGURED";
  error: string;
}

export interface MutationAuthSuccess {
  ok: true;
  mode: "bearer" | "telegram";
  telegramUserId: number | null;
}

export type MutationAuthResult = MutationAuthFailure | MutationAuthSuccess;

export type TelegramInitDataResult =
  | { ok: true; params: Record<string, string> }
  | { ok: false; error: string; params: Record<string, string> };

function parseTelegramInitData(initData: string): Record<string, string> {
  const params = new URLSearchParams(initData);
  const out: Record<string, string> = {};
  for (const [key, value] of params.entries()) {
    out[key] = value;
  }
  return out;
}

function readFirstExistingFile(paths: string[]): string {
  for (const filePath of paths) {
    try {
      if (filePath && existsSync(filePath)) {
        return readFileSync(filePath, "utf8").trim();
      }
    } catch {
      // Ignore unreadable files and continue to next candidate.
    }
  }
  return "";
}

function resolveTelegramBotToken(): string {
  const fromEnv = process.env.TELEGRAM_BOT_TOKEN?.trim();
  if (fromEnv) {
    return fromEnv;
  }

  const configuredPath = process.env.TELEGRAM_BOT_TOKEN_FILE?.trim() || process.env.TELEGRAM_TOKEN_FILE?.trim() || "";
  return readFirstExistingFile([configuredPath, path.join(os.homedir(), ".openclaw", "secrets", "telegram.token")]);
}

function resolveMutationBearerToken(): string {
  return (
    process.env.ORION_API_BEARER_TOKEN?.trim() ||
    process.env.MINIAPP_INGEST_TOKEN?.trim() ||
    process.env.INGEST_TOKEN?.trim() ||
    ""
  );
}

function safeEqual(left: string, right: string): boolean {
  const leftBuffer = Buffer.from(left, "utf8");
  const rightBuffer = Buffer.from(right, "utf8");
  return leftBuffer.length === rightBuffer.length && timingSafeEqual(leftBuffer, rightBuffer);
}

function extractBearerToken(request: Request): string | null {
  const authHeader = (request.headers.get("authorization") || "").trim();
  if (!authHeader) {
    return null;
  }
  const [scheme, value] = authHeader.split(/\s+/, 2);
  if (scheme?.toLowerCase() !== "bearer" || !value) {
    return "";
  }
  return value.trim();
}

export function verifyTelegramInitData(options: {
  initData: string;
  botToken: string;
  maxAgeSec: number;
  clockSkewSec?: number;
  nowMs?: number;
}): TelegramInitDataResult {
  const params = parseTelegramInitData(options.initData);
  const hashRaw = typeof params.hash === "string" ? params.hash : "";
  const expectedHash = hashRaw.trim().toLowerCase();
  if (!expectedHash) {
    return { ok: false, error: "missing_hash", params };
  }

  const pairs: Array<[string, string]> = [];
  for (const [key, value] of Object.entries(params)) {
    if (key === "hash") {
      continue;
    }
    pairs.push([key, String(value)]);
  }
  pairs.sort((a, b) => a[0].localeCompare(b[0]));
  const dataCheckString = pairs.map(([key, value]) => `${key}=${value}`).join("\n");

  const secretKey = createHmac("sha256", "WebAppData").update(String(options.botToken || "")).digest();
  const computedHash = createHmac("sha256", secretKey).update(dataCheckString).digest("hex");
  if (!safeEqual(computedHash, expectedHash)) {
    return { ok: false, error: "bad_sig", params };
  }

  const authDate = Number.parseInt(String(params.auth_date || ""), 10);
  if (!Number.isFinite(authDate) || authDate <= 0) {
    return { ok: false, error: "bad_auth_date", params };
  }

  const nowSec = Math.floor((options.nowMs ?? Date.now()) / 1_000);
  const clockSkewSec = Number.isFinite(options.clockSkewSec) ? Number(options.clockSkewSec) : 60;
  const ageSec = nowSec - authDate;
  if (clockSkewSec >= 0 && ageSec < -clockSkewSec) {
    return { ok: false, error: "future_auth_date", params };
  }
  if (Number.isFinite(options.maxAgeSec) && options.maxAgeSec > 0 && ageSec > options.maxAgeSec) {
    return { ok: false, error: "expired", params };
  }

  return { ok: true, params };
}

function parseTelegramUserId(params: Record<string, string>): number | null {
  const rawUser = params.user;
  if (!rawUser) {
    return null;
  }
  try {
    const user = JSON.parse(rawUser) as { id?: unknown };
    return typeof user.id === "number" && Number.isFinite(user.id) ? user.id : null;
  } catch {
    return null;
  }
}

export function authorizeMutationRequest(request: Request): MutationAuthResult {
  const bearerSecret = resolveMutationBearerToken();
  const telegramBotToken = resolveTelegramBotToken();
  const hasBearerMode = bearerSecret.length > 0;
  const hasTelegramMode = telegramBotToken.length > 0;
  if (!hasBearerMode && !hasTelegramMode) {
    return {
      ok: false,
      status: 503,
      code: "MISCONFIGURED",
      error: "Mutation auth is not configured"
    };
  }

  const bearerToken = extractBearerToken(request);
  if (bearerToken !== null) {
    if (!hasBearerMode) {
      return {
        ok: false,
        status: 503,
        code: "MISCONFIGURED",
        error: "Bearer auth is not configured"
      };
    }
    if (!bearerToken) {
      return {
        ok: false,
        status: 403,
        code: "FORBIDDEN",
        error: "Invalid bearer token"
      };
    }
    if (!safeEqual(bearerToken, bearerSecret)) {
      return {
        ok: false,
        status: 403,
        code: "FORBIDDEN",
        error: "Invalid bearer token"
      };
    }
    return {
      ok: true,
      mode: "bearer",
      telegramUserId: null
    };
  }

  const telegramInitData = (request.headers.get(TELEGRAM_INIT_DATA_HEADER) || "").trim();
  if (telegramInitData) {
    if (!hasTelegramMode) {
      return {
        ok: false,
        status: 503,
        code: "MISCONFIGURED",
        error: "Telegram auth is not configured"
      };
    }
    if (telegramInitData.length > MAX_TELEGRAM_INIT_DATA_LENGTH) {
      return {
        ok: false,
        status: 403,
        code: "FORBIDDEN",
        error: "Invalid telegram initData"
      };
    }

    const verifyResult = verifyTelegramInitData({
      initData: telegramInitData,
      botToken: telegramBotToken,
      maxAgeSec: Number(process.env.TELEGRAM_INITDATA_MAX_AGE_SEC || 24 * 60 * 60),
      clockSkewSec: Number(process.env.TELEGRAM_INITDATA_CLOCK_SKEW_SEC || 60)
    });
    if (!verifyResult.ok) {
      return {
        ok: false,
        status: 403,
        code: "FORBIDDEN",
        error: `Invalid telegram initData (${verifyResult.error})`
      };
    }

    return {
      ok: true,
      mode: "telegram",
      telegramUserId: parseTelegramUserId(verifyResult.params)
    };
  }

  return {
    ok: false,
    status: 401,
    code: "UNAUTHORIZED",
    error: "Missing auth credentials"
  };
}

export function mutationAuthErrorResponse(result: MutationAuthFailure): Response {
  return Response.json(
    {
      error: result.error,
      code: result.code
    },
    { status: result.status }
  );
}
