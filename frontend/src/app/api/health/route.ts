import { NextResponse } from "next/server";
import { DEMO, forward } from "@/lib/upstream";

export const dynamic = "force-dynamic";

export async function GET() {
  if (DEMO) return NextResponse.json({ status: "ok", demo_mode: true });
  const res = await forward("/health", { method: "GET" });
  if (!res.ok) return res;
  const body = await res.json();
  return NextResponse.json({ ...body, demo_mode: false });
}
