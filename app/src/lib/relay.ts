export function relayToken(): string {
  return (
    process.env.MINIAPP_COMMAND_RELAY_TOKEN?.trim() ||
    process.env.MINIAPP_INGEST_TOKEN?.trim() ||
    process.env.INGEST_TOKEN?.trim() ||
    ""
  );
}

export function relayEnabled(): boolean {
  return relayToken().length > 0;
}

export function relayAuthOk(request: Request): boolean {
  const token = relayToken();
  if (!token) {
    return false;
  }

  const auth = request.headers.get("authorization") ?? "";
  const [scheme, value] = auth.split(/\s+/, 2);
  return scheme?.toLowerCase() === "bearer" && value === token;
}

export function relayAgentId(): string {
  const configured = process.env.OPENCLAW_AGENT_ID?.trim();
  return configured && configured.length > 0 ? configured : "main";
}
