export const runtime = "nodejs";

export async function GET(): Promise<Response> {
  try {
    const { getSnapshot } = await import("@orion-core/db");
    const snapshot = getSnapshot();
    return Response.json(snapshot);
  } catch (error) {
    console.error("GET /api/state failed", error);
    return Response.json(
      {
        error: error instanceof Error ? error.message : "Failed to load ORION Core state"
      },
      { status: 500 }
    );
  }
}
