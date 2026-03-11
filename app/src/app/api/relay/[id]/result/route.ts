import { completeDirectiveAction, validateRelayResultRequest } from "@orion-core/db";
import { relayAuthOk, relayEnabled } from "@/lib/relay";

export const runtime = "nodejs";

export async function POST(request: Request, context: { params: Promise<{ id: string }> }): Promise<Response> {
  if (!relayEnabled()) {
    return Response.json(
      { ok: false, error: { code: "DISABLED", message: "Command relay is disabled" } },
      { status: 503 }
    );
  }

  const params = await context.params;
  const id = String(params.id ?? "").trim();
  if (!id) {
    return Response.json(
      { ok: false, error: { code: "BAD_REQUEST", message: "Missing relay command id" } },
      { status: 400 }
    );
  }

  const rawBody = await request.text();
  if (!relayAuthOk(request, rawBody, `/api/relay/${id}/result`)) {
    return Response.json(
      { ok: false, error: { code: "UNAUTHORIZED", message: "Bad relay token" } },
      { status: 401 }
    );
  }

  let body: ReturnType<typeof validateRelayResultRequest>;
  try {
    body = validateRelayResultRequest(rawBody ? JSON.parse(rawBody) : {});
  } catch (error) {
    return Response.json(
      { ok: false, error: { code: "BAD_REQUEST", message: error instanceof Error ? error.message : "Invalid relay result body" } },
      { status: 400 }
    );
  }

  const run = completeDirectiveAction(id, body.workerId, body.claimToken, {
    ok: body.ok,
    code: body.code,
    responseText: body.responseText,
    error: body.error
  });

  if (!run) {
    return Response.json(
      { ok: false, error: { code: "NOT_FOUND", message: "Unknown relay command id or invalid lease" } },
      { status: 404 }
    );
  }

  return Response.json({ ok: true });
}
