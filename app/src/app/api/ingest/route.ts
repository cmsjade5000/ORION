import { authorizeMutationRequest, mutationAuthErrorResponse } from "../../../lib/mutation-auth";

export const runtime = "nodejs";

export async function POST(request: Request): Promise<Response> {
  const auth = authorizeMutationRequest(request);
  if (!auth.ok) {
    return mutationAuthErrorResponse(auth);
  }

  try {
    const payload = (await request.json()) as Record<string, unknown>;
    return Response.json({ ok: true, accepted: true, type: payload?.type ?? null });
  } catch {
    return Response.json({ ok: true, accepted: true, type: null });
  }
}
