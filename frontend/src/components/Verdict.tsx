import type { Label } from "@/lib/types";

const STYLE: Record<Label, string> = {
  true: "bg-ok-soft text-ok",
  false: "bg-bad-soft text-bad",
  unsure: "bg-warn-soft text-warn",
};

export function VerdictBadge({ label }: { label: Label }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${STYLE[label]}`}>
      {label}
    </span>
  );
}

export function ConfidenceBar({ value }: { value: number | null }) {
  if (value === null) return <span className="text-xs text-muted">—</span>;
  // Confidence is 0.5–1 by contract; draw that range across the full bar.
  const pct = Math.max(0, Math.min(1, (value - 0.5) / 0.5)) * 100;
  return (
    <span className="inline-flex items-center gap-2">
      <span className="h-1.5 w-14 overflow-hidden rounded-full bg-line">
        <span className="block h-full rounded-full bg-fg/70" style={{ width: `${pct}%` }} />
      </span>
      <span className="tabular-nums text-xs">{value.toFixed(2)}</span>
    </span>
  );
}
