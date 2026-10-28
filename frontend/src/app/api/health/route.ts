import { NextResponse } from "next/server";
import { DEMO, forward } from "@/lib/upstream";

export const dynamic = "force-dynamic";

export async function GET() {
  // fixtures: true only for this frontend's own demo mode, where uploads are not parsed.
  if (DEMO) return NextResponse.json({ status: "ok", demo_mode: true, fixtures: true });
  const res = await forward("/health", { method: "GET" });
  if (!res.ok) return res;
  const body = await res.json();
  // The API may itself run a synthetic engine (its own ARENA_DEMO); report what it says.
  return NextResponse.json({ ...body, demo_mode: Boolean(body.demo_mode) });
}
