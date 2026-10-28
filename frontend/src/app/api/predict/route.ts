import { NextResponse } from "next/server";
import { DEMO, demoPredict, forward } from "@/lib/upstream";
import type { InputRow } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = await req.text();
  if (DEMO) {
    let rows: InputRow[];
    try {
      rows = JSON.parse(body).rows;
      if (!Array.isArray(rows)) throw new Error();
    } catch {
      return NextResponse.json({ error: 'Expected {"rows": [...]}' }, { status: 400 });
    }
    return NextResponse.json(demoPredict(rows));
  }
  return forward("/predict", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
  });
}
