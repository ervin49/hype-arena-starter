import { CheckCircle2, HelpCircle, Rows3, XCircle, type LucideIcon } from "lucide-react";
import type { computeStats } from "@/lib/format";

function Kpi({ label, value, pct, icon: Icon, bar }: { label: string; value: number; pct: number; icon: LucideIcon; bar: string }) {
  return (
    <div className="card-soft p-5">
      <div className="flex items-start justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span className="grid size-9 place-items-center rounded-xl bg-accent text-primary">
          <Icon className="size-4" />
        </span>
      </div>
      <div className="mt-2 text-3xl font-bold tabular-nums text-heading">{value.toLocaleString("en-US")}</div>
      <div className="mt-4 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div className={`h-full rounded-full ${bar}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-xs font-semibold tabular-nums text-muted-foreground">{pct.toFixed(0)}%</span>
      </div>
    </div>
  );
}

export function KpiCards({ stats }: { stats: ReturnType<typeof computeStats> }) {
  const pct = (n: number) => (stats.total ? (n / stats.total) * 100 : 0);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Rows checked" value={stats.total} pct={stats.total ? 100 : 0} icon={Rows3} bar="bg-primary" />
        <Kpi label="True" value={stats.counts.true} pct={pct(stats.counts.true)} icon={CheckCircle2} bar="bg-primary" />
        <Kpi label="False" value={stats.counts.false} pct={pct(stats.counts.false)} icon={XCircle} bar="bg-track" />
        <Kpi label="Unsure" value={stats.counts.unsure} pct={pct(stats.counts.unsure)} icon={HelpCircle} bar="bg-indigo" />
      </div>
      <p className="text-sm text-muted-foreground">
        Avg. confidence of firm verdicts{" "}
        <span className="font-bold tabular-nums text-heading">{stats.avg == null ? "—" : stats.avg.toFixed(2)}</span>
      </p>
    </div>
  );
}
