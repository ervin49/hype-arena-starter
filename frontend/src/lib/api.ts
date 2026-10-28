import type { ClaimsResponse, MetricsResponse, PredictCsvResponse } from "./types";

// Browser-side calls to this app's own /api routes (see src/app/api/).
// No fallback: a failure is thrown and shown as an error, never as results.

export class EngineError extends Error {
  detail?: string;
  constructor(message: string, detail?: string) {
    super(message);
    this.detail = detail;
  }
}

export interface EngineFailure {
  message: string;
  detail?: string;
}

export interface Health {
  status: string;
  demo_mode: boolean;
}

async function json(res: Response): Promise<Record<string, unknown>> {
  try {
    return await res.json();
  } catch {
    throw new EngineError(`HTTP ${res.status}: the response is not JSON.`);
  }
}

export async function getHealth(): Promise<Health> {
  const res = await fetch("/api/health", { cache: "no-store" });
  const body = await json(res);
  if (!res.ok) throw new EngineError(String(body.error ?? `HTTP ${res.status}`), body.detail as string | undefined);
  return { status: String(body.status), demo_mode: Boolean(body.demo_mode) };
}

export async function predictCsv(file: File): Promise<PredictCsvResponse> {
  const form = new FormData();
  form.append("file", file);
  let res: Response;
  try {
    res = await fetch("/api/predict/csv", { method: "POST", body: form });
  } catch (e) {
    throw new EngineError("The request failed.", e instanceof Error ? e.message : String(e));
  }
  const body = await json(res);
  if (!res.ok) throw new EngineError(String(body.error ?? `HTTP ${res.status}`), body.detail as string | undefined);
  return body as unknown as PredictCsvResponse;
}

export async function getClaims(): Promise<ClaimsResponse> {
  let res: Response;
  try {
    res = await fetch("/api/claims", { cache: "no-store" });
  } catch (e) {
    throw new EngineError("The request failed.", e instanceof Error ? e.message : String(e));
  }
  const body = await json(res);
  if (!res.ok) throw new EngineError(String(body.error ?? `HTTP ${res.status}`), body.detail as string | undefined);
  return body as unknown as ClaimsResponse;
}

export async function getMetrics(): Promise<MetricsResponse> {
  let res: Response;
  try {
    res = await fetch("/api/metrics", { cache: "no-store" });
  } catch (e) {
    throw new EngineError("The request failed.", e instanceof Error ? e.message : String(e));
  }
  const body = await json(res);
  if (!res.ok) throw new EngineError(String(body.error ?? `HTTP ${res.status}`), body.detail as string | undefined);
  return body as unknown as MetricsResponse;
}
