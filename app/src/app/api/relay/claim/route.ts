import { claimDirectiveAction } from "@orion-core/db";
import { relayAgentId, relayAuthOk, relayEnabled } from "@/lib/relay";

export const runtime = "nodejs";

export async function POST(request: Request): Promise<Response> {
  if (!relayEnabled()) {
    return Response.json(
      { ok: false, error: { code: "DISABLED", message: "Command relay is disabled" } },
      { status: 503 }
    );
  }

  if (!relayAuthOk(request)) {
    return Response.json(
      { ok: false, error: { code: "UNAUTHORIZED", message: "Bad relay token" } },
      { status: 401 }
    );
  }

  const body = (await request.json().catch(() => ({}))) as { workerId?: string };
  const workerId = typeof body.workerId === "string" && body.workerId.trim().length > 0 ? body.workerId.trim() : "relay-worker";
  const run = claimDirectiveAction(workerId);
  if (!run || !run.commandText || !run.deliverTarget) {
    return Response.json({ ok: true, command: null });
  }

  return Response.json({
    ok: true,
    command: {
      id: run.id,
      text: run.commandText,
      deliverTarget: run.deliverTarget,
      agentId: relayAgentId(),
      acceptedAt: new Date(run.createdAt).getTime(),
      leaseUntil: Date.now() + 60_000
    }
  });
}
