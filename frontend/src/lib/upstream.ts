// Server-side only: imported by route handlers, never by client components.
import { NextResponse } from "next/server";
import fixture from "../../fixtures/predict-csv.json";
import type { InputRow, PredictCsvResponse, PredictResponse } from "./types";

// Demo mode is opt-in (ARENA_DEMO=1). It is never a fallback: when the real
// API is configured and fails, the error goes to the UI as an error.
export const DEMO = process.env.ARENA_DEMO === "1";

const API_URL = (process.env.ARENA_API_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const TIMEOUT_MS = Number(process.env.ARENA_API_TIMEOUT_MS ?? 120_000);

export async function forward(path: string, init: RequestInit): Promise<NextResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (e) {
    const timedOut = e instanceof Error && e.name === "TimeoutError";
    return NextResponse.json(
      { error: timedOut ? "The engine API timed out." : "The engine API is unreachable." },
      { status: timedOut ? 504 : 502 },
    );
  }
  const body = await res.text();
  if (!res.ok) {
    return NextResponse.json(
      { error: `The engine API answered ${res.status}.`, detail: extractDetail(body) },
      { status: res.status >= 500 ? 502 : res.status },
    );
  }
  return new NextResponse(body, {
    status: 200,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
}

// FastAPI errors carry {"detail": ...}; pass that text through, nothing else.
function extractDetail(body: string): string | undefined {
  try {
    const d = JSON.parse(body)?.detail;
    if (d === undefined) return undefined;
    return typeof d === "string" ? d : JSON.stringify(d);
  } catch {
    return body.slice(0, 500) || undefined;
  }
}

export function demoCsv(): PredictCsvResponse {
  const { rows, predictions } = fixture as unknown as PredictCsvResponse;
  return { rows, predictions, demo_mode: true };
}

// Synthetic verdicts for whatever rows were sent, cycling through the fixture
// so every UI state is exercised. Labelled rows get no prediction, as in the API.
export function demoPredict(rows: InputRow[]): PredictResponse {
  const pool = demoCsv().predictions;
  const predictions = rows
    .filter((r) => r.label === "")
    .map((r, i) => ({ ...pool[i % pool.length], id: r.id, evidence_ids: [] }));
  return { predictions, demo_mode: true };
}
