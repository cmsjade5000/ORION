import { authorizeMutationRequest, mutationAuthErrorResponse } from "../../../../lib/mutation-auth";

export const runtime = "nodejs";

export async function POST(request: Request): Promise<Response> {
  const auth = authorizeMutationRequest(request);
  if (!auth.ok) {
    return mutationAuthErrorResponse(auth);
  }

  try {
    const { appendEvent, getSnapshot } = await import("@orion-core/db");
    const { isPatchId } = await import("@orion-core/db/patches");
    const body = (await request.json()) as { patchId?: string };
    if (!body.patchId || !isPatchId(body.patchId)) {
      return Response.json({ error: "Invalid patchId" }, { status: 400 });
    }

    appendEvent({ type: "PATCH_APPLIED", payload: { patchId: body.patchId } });
    return Response.json(getSnapshot());
  } catch (error) {
    return Response.json(
      {
        error: error instanceof Error ? error.message : "Failed to apply patch"
      },
      { status: 500 }
    );
  }
}
