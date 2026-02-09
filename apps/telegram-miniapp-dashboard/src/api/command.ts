export type AcceptedEnvelope = {
  ok: true;
  status: "accepted";
  requestId: string;
  accepted: {
    id: string;
    receivedAt: number;
  };
  routing: {
    target: "ORION";
    mode: "task_packet";
    taskPacketId: string | null;
    sessionId: string | null;
  };
};

export type RejectedEnvelope = {
  ok: false;
  error: {
    code: string;
    message: string;
  };
};

export async function submitCommand(opts: {
  initData: string;
  text: string;
  clientTs?: number;
  meta?: Record<string, unknown>;
}): Promise<AcceptedEnvelope> {
  const res = await fetch("/api/command", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-telegram-init-data": opts.initData,
    },
    body: JSON.stringify({
      text: opts.text,
      clientTs: opts.clientTs ?? Date.now(),
      meta: opts.meta ?? {},
    }),
  });

  const data = (await res.json()) as AcceptedEnvelope | RejectedEnvelope;
  if (!res.ok || !data.ok) {
    const msg = !data.ok ? `${data.error.code}: ${data.error.message}` : `HTTP ${res.status}`;
    throw new Error(`command rejected: ${msg}`);
  }

  return data;
}
