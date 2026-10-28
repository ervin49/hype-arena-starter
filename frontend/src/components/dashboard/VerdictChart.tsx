import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { MonthPoint } from "@/lib/format";
import { cn } from "@/lib/utils";

const RANGES = { "1M": 1, "3M": 3, "6M": 6, "1Y": 12, All: Infinity } as const;
type Range = keyof typeof RANGES;

export function VerdictChart({ data }: { data: MonthPoint[] }) {
  const [range, setRange] = useState<Range>("All");
  const shown = useMemo(() => {
    if (!data.length || range === "All") return data;
    const last = new Date(`${data[data.length - 1]!.key}-01T00:00:00`);
    const from = new Date(last);
    from.setMonth(from.getMonth() - RANGES[range] + 1);
    const fromKey = `${from.getFullYear()}-${String(from.getMonth() + 1).padStart(2, "0")}`;
    return data.filter((d) => d.key >= fromKey);
  }, [data, range]);

  const totalTrue = shown.reduce((a, d) => a + d.true, 0);
  const total = shown.reduce((a, d) => a + d.true + d.false + d.unsure, 0);

  return (
    <div className="card-soft p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">Verdicts over time</h2>
          <div className="mt-1 flex items-center gap-4 text-xs text-muted-foreground">
            <Key cls="bg-primary" label="True" />
            <Key cls="bg-track" label="False" />
            <Key cls="bg-indigo" label="Unsure" />
          </div>
        </div>
        <div className="flex gap-1 rounded-full bg-muted p-1">
          {(Object.keys(RANGES) as Range[]).map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-semibold transition",
                r === range ? "bg-primary text-primary-foreground shadow-soft" : "text-muted-foreground hover:text-primary",
              )}
            >
              {r}
            </button>
          ))}
        </div>
      </div>
      <div className="relative mt-4 h-64">
        {total > 0 && (
          <span className="absolute right-2 top-0 z-10 rounded-full bg-heading px-3 py-1 text-xs font-semibold text-card">
            True share {((totalTrue / total) * 100).toFixed(1)}%
          </span>
        )}
        {shown.length === 0 ? (
          <div className="grid h-full place-items-center text-sm text-muted-foreground">
            {data.length === 0 ? "Upload a CSV to see verdicts by month" : "No checked rows in this range"}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={shown} barGap={6} margin={{ top: 28, left: -20, right: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="4 4" />
              <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
              <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
              <Tooltip
                cursor={{ fill: "var(--muted)" }}
                contentStyle={{ background: "var(--card)", border: "none", borderRadius: 14, boxShadow: "var(--shadow-card)", fontSize: 12 }}
              />
              <Bar dataKey="true" name="True" fill="var(--primary)" radius={[8, 8, 8, 8]} maxBarSize={18} />
              <Bar dataKey="false" name="False" fill="var(--track)" radius={[8, 8, 8, 8]} maxBarSize={18} />
              <Bar dataKey="unsure" name="Unsure" fill="var(--indigo)" radius={[8, 8, 8, 8]} maxBarSize={18} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

function Key({ cls, label }: { cls: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`size-2 rounded-full ${cls}`} />
      {label}
    </span>
  );
}
