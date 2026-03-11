import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";

const RELAY_HEADER_TIMESTAMP = "x-orion-relay-timestamp";
const RELAY_HEADER_NONCE = "x-orion-relay-nonce";
const RELAY_HEADER_SIGNATURE = "x-orion-relay-signature";
const MAX_SIGNATURE_AGE_MS = 5 * 60_000;
const NONCE_CACHE_TTL_MS = 10 * 60_000;

const seenNonces = new Map<string, number>();

function cleanExpiredNonces(now = Date.now()): void {
  for (const [nonce, expiresAt] of seenNonces.entries()) {
    if (expiresAt <= now) {
      seenNonces.delete(nonce);
    }
  }
}

function relaySecret(): string {
  return (
    process.env.MINIAPP_COMMAND_RELAY_TOKEN?.trim() ||
    process.env.MINIAPP_INGEST_TOKEN?.trim() ||
    process.env.INGEST_TOKEN?.trim() ||
    ""
  );
}

export function relayToken(): string {
  return relaySecret();
}

export function relayEnabled(): boolean {
  return relaySecret().length > 0;
}

function buildRelaySignature(secret: string, method: string, path: string, timestamp: string, nonce: string, body: string): string {
  return createHmac("sha256", secret).update([timestamp, nonce, method.toUpperCase(), path, body].join(".")).digest("hex");
}

export function buildRelayAuthHeaders(method: string, path: string, body: string): Record<string, string> {
  const secret = relaySecret();
  if (!secret) {
    return {};
  }
  const timestamp = new Date().toISOString();
  const nonce = randomUUID();
  const signature = buildRelaySignature(secret, method, path, timestamp, nonce, body);
  return {
    authorization: `Bearer ${secret}`,
    [RELAY_HEADER_TIMESTAMP]: timestamp,
    [RELAY_HEADER_NONCE]: nonce,
    [RELAY_HEADER_SIGNATURE]: signature
  };
}

export function relayAuthOk(request: Request, body: string, path: string): boolean {
  const secret = relaySecret();
  if (!secret) {
    return false;
  }

  const auth = request.headers.get("authorization") ?? "";
  const [scheme, value] = auth.split(/\s+/, 2);
  if (scheme?.toLowerCase() !== "bearer" || value !== secret) {
    return false;
  }

  const timestamp = request.headers.get(RELAY_HEADER_TIMESTAMP) ?? "";
  const nonce = request.headers.get(RELAY_HEADER_NONCE) ?? "";
  const signature = request.headers.get(RELAY_HEADER_SIGNATURE) ?? "";
  if (!timestamp || !nonce || !signature) {
    return false;
  }

  const parsed = Date.parse(timestamp);
  if (!Number.isFinite(parsed) || Math.abs(Date.now() - parsed) > MAX_SIGNATURE_AGE_MS) {
    return false;
  }

  cleanExpiredNonces();
  if (seenNonces.has(nonce)) {
    return false;
  }

  const expected = buildRelaySignature(secret, request.method, path, timestamp, nonce, body);
  const actualBuffer = Buffer.from(signature, "hex");
  const expectedBuffer = Buffer.from(expected, "hex");
  if (actualBuffer.length !== expectedBuffer.length || !timingSafeEqual(actualBuffer, expectedBuffer)) {
    return false;
  }

  seenNonces.set(nonce, Date.now() + NONCE_CACHE_TTL_MS);
  return true;
}

export function relayAgentId(): string {
  const configured = process.env.OPENCLAW_AGENT_ID?.trim();
  return configured && configured.length > 0 ? configured : "main";
}
