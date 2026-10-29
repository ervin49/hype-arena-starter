import type { Claim, Prediction } from "./arena";

// The six official output.csv columns, written as arena/io.py writes them:
// predictions first (no type/text/form), then claims; confidence in 0.5–1,
// at most 3 decimals, empty for unsure.
const COLUMNS = ["id", "type", "text", "form", "label", "confidence"] as const;
type OutputRow = Record<(typeof COLUMNS)[number], string>;

function confidenceCell(label: string, c: number | null | undefined): string {
  if (label === "unsure" || c == null || Number.isNaN(c)) return "";
  return Math.min(1, Math.max(0.5, c)).toFixed(3).replace(/\.?0+$/, "");
}

function predictionRows(predictions: Prediction[]): OutputRow[] {
  const seen = new Set<string>();
  return predictions.flatMap((p) => {
    if (seen.has(p.id)) return [];
    seen.add(p.id);
    let label: string = p.label || "unsure";
    const confidence = confidenceCell(label, p.confidence);
    if (label !== "unsure" && !confidence) label = "unsure";
    return [{ id: p.id, type: "", text: "", form: "", label, confidence }];
  });
}

function claimRows(claims: Claim[]): OutputRow[] {
  return claims.map((c) => ({
    id: c.id,
    type: c.type,
    text: c.text,
    form: typeof c.form === "string" ? c.form : JSON.stringify(c.form),
    label: "true",
    confidence: confidenceCell("true", c.confidence) || "0.5",
  }));
}

const cell = (v: string) => (/[",\r\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);

export function outputCsv(predictions: Prediction[], claims: Claim[] = []): string {
  const rows = [...predictionRows(predictions), ...claimRows(claims)];
  return [COLUMNS.join(","), ...rows.map((r) => COLUMNS.map((c) => cell(r[c])).join(","))].join("\r\n") + "\r\n";
}

export function downloadCsv(name: string, csv: string) {
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
