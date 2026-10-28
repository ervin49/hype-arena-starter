import { useState } from "react";
import type { InputRow, Label, Prediction } from "@/lib/types";
import { confFraction } from "@/lib/format";
import { cn } from "@/lib/utils";
import { VerdictPill } from "./VerdictPill";

type Filter = "all" | Label;

const PAGE = 8;

export function VerdictsTable({ items, selectedId, onSelect, subtitle, simulated, emptyText }: {
  items: { row: InputRow; pred: Prediction }[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  subtitle?: string;
  simulated: boolean;
  emptyText: string;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const [showAll, setShowAll] = useState(false);
  const count = (f: Filter) => (f === "all" ? items.length : items.filter((i) => i.pred.label === f).length);
  const filtered = items.filter((i) => filter === "all" || i.pred.label === filter);
  const shown = showAll ? filtered : filtered.slice(0, PAGE);

  return (
    <div id="results" className="card-soft scroll-mt-6 p-5 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-bold">
            Latest verdicts
            {simulated && <span className="rounded-full bg-warn-soft px-2 py-0.5 text-[11px] font-semibold text-warn">simulated</span>}
          </h2>
          {subtitle && <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>}
        </div>
        {filtered.length > PAGE && (
          <button onClick={() => setShowAll((s) => !s)} className="shrink-0 text-sm font-semibold text-primary hover:underline">
            {showAll ? "Show less" : `See all ${filtered.length}`}
          </button>
        )}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {(["all", "true", "false", "unsure"] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-semibold transition",
              f === filter ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-primary",
            )}
          >
            {f === "all" ? "All" : f} <span className="tabular-nums opacity-70">{count(f)}</span>
          </button>
        ))}
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-sm">
          <thead className="text-xs text-muted-foreground">
            <tr>
              <th className="pb-2 font-medium">Row</th>
              <th className="pb-2 font-medium">Date</th>
              <th className="pb-2 font-medium">Verdict</th>
              <th className="pb-2 font-medium">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {shown.map(({ row, pred }) => (
              <tr
                key={row.id}
                onClick={() => onSelect(row.id)}
                className={cn("cursor-pointer border-t transition hover:bg-muted/60", selectedId === row.id && "bg-accent")}
              >
                <td className="max-w-xs py-3 pr-4">
                  <div className="font-mono text-[11px] text-muted-foreground">{row.id}</div>
                  <div className="line-clamp-2 font-medium text-heading">{row.text}</div>
                </td>
                <td className="whitespace-nowrap py-3 pr-4 tabular-nums text-muted-foreground">{row.date}</td>
                <td className="py-3 pr-4">
                  <VerdictPill label={pred.label} />
                </td>
                <td className="py-3">
                  {pred.confidence == null ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-track">
                        <div className="h-full rounded-full bg-primary" style={{ width: `${confFraction(pred.confidence) * 100}%` }} />
                      </div>
                      <span className="text-xs font-semibold tabular-nums">{pred.confidence.toFixed(2)}</span>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {shown.length === 0 && (
              <tr>
                <td colSpan={4} className="py-8 text-center text-muted-foreground">
                  {items.length === 0 ? emptyText : "No rows match."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
