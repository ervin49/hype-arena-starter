import { NextResponse } from "next/server";
import fixture from "../../../../fixtures/metrics.json";
import { DEMO, forward } from "@/lib/upstream";

export const dynamic = "force-dynamic";

// The fixture is opt-in (ARENA_METRICS_FIXTURE=1, or the whole frontend in demo
// mode) and always flagged simulated. Otherwise the API's numbers pass through,
// and an API without /metrics is reported as an error, never filled in.
const FIXTURE = DEMO || process.env.ARENA_METRICS_FIXTURE === "1";

export async function GET() {
  if (FIXTURE)
    return NextResponse.json({ labels: fixture.labels, claims: fixture.claims, shift: null, controls: null, simulated: true });
  const res = await forward("/metrics", { method: "GET" });
  if (!res.ok) return res;
  const body = await res.json();
  return NextResponse.json({
    labels: body.labels ?? null,
    claims: body.claims ?? null,
    shift: body.shift ?? null,
    controls: body.controls ?? null,
    simulated: false,
  });
}
