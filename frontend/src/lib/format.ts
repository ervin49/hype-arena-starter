import type { ClaimedValue } from "./types";

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
      return `${op}v${v.value}`;
    default:
      return `${op}${String(v.value)}`;
  }
}

function num(x: unknown): string {
  return typeof x === "number" ? x.toLocaleString("en-US") : String(x);
}

export function formatConfidence(c: number | null): string {
  return c === null ? "—" : c.toFixed(2);
}
