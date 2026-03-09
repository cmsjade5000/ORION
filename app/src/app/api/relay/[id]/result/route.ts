import { completeDirectiveAction } from "@orion-core/db";
import { relayAuthOk, relayEnabled } from "@/lib/relay";

export const runtime = "nodejs";

export async function POST(request: Request, context: { params: Promise<{ id: string }> }): Promise<Response> {
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

  const params = await context.params;
  const id = String(params.id ?? "").trim();
  if (!id) {
    return Response.json(
      { ok: false, error: { code: "BAD_REQUEST", message: "Missing relay command id" } },
      { status: 400 }
    );
  }

  const body = (await request.json().catch(() => ({}))) as {
    ok?: boolean;
    code?: number | null;
    responseText?: string | null;
    error?: string | null;
  };

  const run = completeDirectiveAction(id, {
    ok: Boolean(body.ok),
    code: typeof body.code === "number" ? body.code : null,
    responseText: typeof body.responseText === "string" ? body.responseText : null,
    error: typeof body.error === "string" ? body.error : null
  });

  if (!run) {
    return Response.json(
      { ok: false, error: { code: "NOT_FOUND", message: "Unknown relay command id" } },
      { status: 404 }
    );
  }

  return Response.json({ ok: true });
}
