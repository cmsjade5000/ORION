import type { LiveState } from "./state";

type StreamAuthOk = {
  ok: true;
  token: string;
  expiresAt: number;
};

type StreamAuthErr = {
  ok: false;
  error: { code: string; message: string };
};

export type StreamStatus = "connecting" | "open" | "error" | "closed";

/**
 * Event stream handshake.
 *
 * EventSource can't send custom headers, so we do a short-lived token exchange:
 * - POST /api/sse-auth with `x-telegram-init-data`
 * - server returns a short-lived token
 * - client opens EventSource /api/events?token=...
 */
export async function getStreamToken(initData: string): Promise<StreamAuthOk> {
  const res = await fetch("/api/sse-auth", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-telegram-init-data": initData,
    },
    body: JSON.stringify({}),
  });

  const data = (await res.json()) as StreamAuthOk | StreamAuthErr;
  if (!res.ok || !data.ok) {
    const msg = !data.ok ? `${data.error.code}: ${data.error.message}` : `HTTP ${res.status}`;
    throw new Error(`stream auth failed: ${msg}`);
  }

  return data;
}

export function connectStateStream(opts: {
  token: string;
  onState: (s: LiveState) => void;
  onStatus?: (st: StreamStatus) => void;
}) {
  if (typeof EventSource === "undefined") {
    throw new Error("EventSource not supported");
  }

  const url = `/api/events?token=${encodeURIComponent(opts.token)}`;
  const es = new EventSource(url);

  opts.onStatus?.("connecting");

  const onOpen = () => opts.onStatus?.("open");
  const onErr = () => opts.onStatus?.("error");

  // Custom events: `event: state`
  const onState = (ev: MessageEvent) => {
    try {
      opts.onState(JSON.parse(String(ev.data)) as LiveState);
    } catch {
      // ignore malformed frames
    }
  };

  es.addEventListener("state", onState as EventListener);
  es.addEventListener("open", onOpen as EventListener);
  es.addEventListener("error", onErr as EventListener);

  return {
    close: () => {
      es.close();
      es.removeEventListener("state", onState as EventListener);
      es.removeEventListener("open", onOpen as EventListener);
      es.removeEventListener("error", onErr as EventListener);
    },
  };
}
