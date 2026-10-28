import type { ClaimedValue, Label, PredictCsvResponse } from "./types";

const CURRENCY: Record<string, string> = { EUR: "€", USD: "$", GBP: "£" };

const OP: Record<string, string> = {
  lt: "under ",
  le: "up to ",
  gt: "over ",
  ge: "at least ",
};

// Human-readable rendering of a claimed value for display only. The engine
// owns the canonical form; this never feeds back into a verdict.
export function formatValue(v: ClaimedValue): string {
  const op = v.op && v.op !== "eq" ? OP[v.op] : "";
  switch (v.kind) {
    case "money": {
      const sym = v.currency ? (CURRENCY[v.currency] ?? `${v.currency} `) : "";
      const per = v.per ? ` / ${v.per}` : "";
      return `${op}${sym}${num(v.value)}${per}`;
    }
    case "percent":
      return `${op}${num(v.value)}%`;
    case "quantity":
    case "duration":
      return `${op}${num(v.value)} ${v.unit ?? ""}`.trim();
    case "boolean":
      return v.value ? "yes" : "no";
    case "version":
      return `${op}v${String(v.value).replace(/^v/, "")}`;
    default:
      return `${op}${String(v.value)}`;
  }
}

function num(x: unknown): string {
  return typeof x === "number" ? x.toLocaleString("en-US") : String(x);
}

// Fill fraction for bars and the gauge: the confidence itself, so 0.65 fills 65%.
export const confFraction = (c: number | null) => (c == null ? 0 : Math.max(0, Math.min(1, c)));

export function computeStats(r: PredictCsvResponse) {
  const counts: Record<Label, number> = { true: 0, false: 0, unsure: 0 };
  r.predictions.forEach((p) => counts[p.label]++);
  const confs = r.predictions.map((p) => p.confidence).filter((c): c is number => c != null);
  const avg = confs.length ? confs.reduce((a, b) => a + b, 0) / confs.length : null;
  return { total: r.predictions.length, counts, avg };
}

export interface MonthPoint {
  key: string;
  month: string;
  true: number;
  false: number;
  unsure: number;
}

// Verdict counts per month of the checked row's date.
export function byMonth(r: PredictCsvResponse): MonthPoint[] {
  const dates = new Map(r.rows.map((x) => [x.id, x.date]));
  const m = new Map<string, MonthPoint>();
  for (const p of r.predictions) {
    const d = dates.get(p.id);
    if (!d) continue;
    const key = d.slice(0, 7);
    if (!m.has(key)) {
      const dt = new Date(`${key}-01T00:00:00`);
      m.set(key, { key, month: dt.toLocaleString("en", { month: "short", year: "2-digit" }), true: 0, false: 0, unsure: 0 });
    }
    m.get(key)![p.label]++;
  }
  return [...m.values()].sort((a, b) => a.key.localeCompare(b.key));
}
