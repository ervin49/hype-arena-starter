import { NextResponse } from "next/server";
import { DEMO, forward } from "@/lib/upstream";

export const dynamic = "force-dynamic";

// The claims the batch run writes, built by the API at startup. This frontend's own
// demo mode has no fixture for them: it answers with none, flagged as demo.
export async function GET() {
  if (DEMO) return NextResponse.json({ claims: [], report: {}, as_of: "", demo_mode: true });
  return forward("/claims", { method: "GET" });
}
