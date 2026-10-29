// Shapes from the Hype Arena API contract (api/README.md). Field names are fixed.
export type Label = "true" | "false" | "unsure";

export interface InputRow {
  id: string;
  text: string;
  date: string;
  label: "" | Label;
}
export interface Fact {
  subject: string;
  attribute: string;
  value: {
    kind: string;
    value: string | number | boolean;
    unit?: string;
    currency?: string;
    per?: string;
    op?: string;
  };
}
export interface EvidenceRow {
  id: string;
  text: string;
  date: string;
  label: "" | Label;
}
export interface Prediction {
  id: string;
  label: Label;
  confidence: number | null;
  evidence_ids: string[];
  evidence?: EvidenceRow[];
  reason: string;
  extraction?: { facts: Fact[]; complete: boolean; issues: string[] };
  error?: string;
}
export interface Claim {
  id: string;
  type: "fact" | "compare" | "change" | "at_event" | "relation";
  text: string;
  form: Record<string, unknown>;
  confidence: number;
  evidence_ids: string[];
  evidence: EvidenceRow[];
}
export interface ClaimsResponse {
  claims: Claim[];
  report: Record<string, number>;
  as_of: string;
  demo_mode: boolean;
}

// GET /metrics: what was measured, each part null when its report is not written yet.
export interface LabelBin {
  label: Label;
  from: number;
  to: number;
  n: number;
  accuracy: number;
  confidence: number;
}
export interface LabelCalibration {
  method: string;
  fitted_on: string;
  rows?: number;
  // out of fold: each practice row labelled by a model that never saw it
  accuracy: number;
  bins: LabelBin[];
  ece_before: number;
  ece_after: number;
}
export interface ClaimGroup {
  group: string;
  // the full judge: all practice rows, the ones that built the claims too
  n: number;
  right: number;
  precision: number | null;
  // the strict judge: only rows dated after the cut-off, which the generator never saw
  strict_n?: number;
  strict_right?: number;
  strict_precision?: number | null;
  confidence: number;
}
export interface ClaimCalibration {
  cutoffs: string[];
  unverified_cap?: number;
  groups: ClaimGroup[];
}
export interface ShiftSummary {
  n: number;
  said: number;
  right: number;
  ece: number;
}
export interface ShiftScenario {
  scenario: string;
  always_true: number;
  unseen_before: ShiftSummary;
  unseen_after: ShiftSummary;
}
export interface ControlReport {
  control_rows: number;
  control_answers: number;
  accuracy: number | null;
  said: number;
  factors?: Record<string, number> | null;
  note?: string;
}
export interface MetricsResponse {
  labels: LabelCalibration | null;
  claims: ClaimCalibration | null;
  shift?: ShiftScenario[] | null;
  controls?: ControlReport | null;
}

// The dev server proxies /api to the FastAPI engine (vite.config.ts, ARENA_API_URL), so the
// browser stays on one origin. Another base can be set in the top bar.
const KEY = "arena.apiBase";
export const DEFAULT_API = "/api";
export const getApiBase = () =>
  (typeof window !== "undefined" && window.localStorage.getItem(KEY)) || DEFAULT_API;
export const setApiBase = (v: string) => window.localStorage.setItem(KEY, v.replace(/\/$/, ""));

// No fallback: a failure is thrown and shown as an error, never as results.
async function req<T>(path: string, init?: RequestInit, timeoutMs = 15_000): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    let r: Response;
    try {
      r = await fetch(getApiBase() + path, { ...init, signal: ctrl.signal });
    } catch (e) {
      throw new Error(
        ctrl.signal.aborted
          ? `The engine API timed out after ${timeoutMs / 1000} s.`
          : "The engine API is unreachable.",
      );
    }
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      if (typeof body.detail === "string") throw new Error(body.detail);
      throw new Error(
        r.status === 502 || r.status === 504
          ? `The engine API is unreachable (HTTP ${r.status}). Start it: .venv/bin/uvicorn api.main:app --port 8000`
          : `The engine API answered HTTP ${r.status}.`,
      );
    }
    return (await r.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

export const api = {
  health: () => req<{ status: string; demo_mode: boolean }>("/health"),
  claims: () => req<ClaimsResponse>("/claims", undefined, 60_000),
  metrics: () => req<MetricsResponse>("/metrics"),
  // the real engine labels a batch in seconds to a couple of minutes
  predict: (rows: InputRow[]) =>
    req<{ predictions: Prediction[]; demo_mode: boolean }>(
      "/predict",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rows }),
      },
      120_000,
    ),
};

export function parseCsv(text: string): InputRow[] {
  const out: string[][] = [];
  let row: string[] = [],
    cell = "",
    q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (c === '"') q = false;
      else cell += c;
    } else if (c === '"') q = true;
    else if (c === ",") {
      row.push(cell);
      cell = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(cell);
      cell = "";
      if (row.some((x) => x.trim())) out.push(row);
      row = [];
    } else cell += c;
  }
  row.push(cell);
  if (row.some((x) => x.trim())) out.push(row);
  const [head, ...body] = out;
  if (!head) return [];
  const idx = (k: string) => head.findIndex((h) => h.replace(/^﻿/, "").trim().toLowerCase() === k);
  const ii = idx("id"),
    it = idx("text"),
    id = idx("date"),
    il = idx("label");
  if (it < 0) throw new Error("CSV needs at least a 'text' column");
  return body.map((r, n) => ({
    id: (ii >= 0 && r[ii]?.trim()) || `row-${n + 1}`,
    text: r[it]?.trim() ?? "",
    date: (id >= 0 && r[id]?.trim()) || new Date().toISOString().slice(0, 10),
    label: ((il >= 0 && r[il]?.trim().toLowerCase()) || "") as InputRow["label"],
  }));
}

export const pct = (x: number | null | undefined, d = 0) =>
  x == null ? "—" : `${(x * 100).toFixed(d)}%`;
export const num = (x: number) => x.toLocaleString("en-US");
