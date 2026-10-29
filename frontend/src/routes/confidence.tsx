import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { motion } from "motion/react";
import fixture from "@/data/metrics.json";
import { api, pct } from "@/lib/arena";
import { Counter, PageHeader, Panel, Reveal, ease } from "@/components/arena/ui";

export const Route = createFileRoute("/confidence")({
  head: () => ({
    meta: [
      { title: "Confidence — Hype Arena" },
      { name: "description", content: "Calibration of label and claim confidence, measured out of fold." },
      { property: "og:title", content: "Confidence — Hype Arena" },
      { property: "og:description", content: "How well Hype Arena's confidence matches reality." },
    ],
  }),
  component: Conf,
});

type Bin = { label: string; from: number; to: number; n: number; accuracy: number; confidence: number };
type Group = { group: string; n: number; right: number; precision: number; confidence: number };
const tip = { contentStyle: { background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }, cursor: { fill: "var(--accent)", opacity: 0.4 } };

// Accuracy of the answers with this label whose confidence falls in [from, to), pooled over bins.
function pooled(bins: Bin[], label: string, from: number, to: number) {
  const sel = bins.filter((b) => b.label === label && b.from >= from && b.to <= to);
  const n = sel.reduce((s, b) => s + b.n, 0);
  return { n, accuracy: n ? sel.reduce((s, b) => s + b.accuracy * b.n, 0) / n : null };
}

function Conf() {
  const q = useQuery({ queryKey: ["metrics"], queryFn: api.metrics, retry: false, enabled: typeof window !== "undefined" });
  const live = q.data as { labels?: { bins: Bin[]; ece_before: number; ece_after: number }; claims?: { groups: Group[] } } | undefined;
  const labels = live?.labels ?? (fixture.labels as { bins: Bin[]; ece_before: number; ece_after: number });
  const groups = live?.claims?.groups ?? (fixture.claims.groups as Group[]);
  const simulated = !live?.labels;
  const bins = labels.bins.map((b) => ({ band: `${b.label} ${b.from}–${b.to}`, Accuracy: +(b.accuracy * 100).toFixed(1), Confidence: +(b.confidence * 100).toFixed(1), n: b.n }));
  const falseMid = pooled(labels.bins, "false", 0.5, 0.8);
  const trueLow = pooled(labels.bins, "true", 0.5, 0.6);

  return (
    <>
      <PageHeader eyebrow="GET /metrics" title="Confidence & calibration">
        {simulated && <span className="rounded-full border border-verdict-unsure/30 bg-verdict-unsure/10 px-3 py-1 font-mono text-xs text-verdict-unsure">fixture · engine offline</span>}
      </PageHeader>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          ["ECE before calibration", labels.ece_before, "lower is better"],
          ["ECE after calibration", labels.ece_after, "Platt, cross-fitted"],
          ["Claim confidence (mean)", 0.959, "measured on unseen rows"],
        ].map(([k, v, s], i) => (
          <Reveal key={k as string} delay={i * 0.05}>
            <div className="panel p-5">
              <div className="eyebrow">{k}</div>
              <div className="mt-2 text-4xl font-semibold"><Counter value={v as number} decimals={3} /></div>
              <div className="mt-1 text-xs text-muted-foreground">{s}</div>
            </div>
          </Reveal>
        ))}
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <Reveal delay={0.15} className="lg:col-span-3">
          <Panel title="Reliability by confidence band" hint="When the engine says 0.9, it should be right ~90% of the time">
            <div className="h-72">
              <ResponsiveContainer>
                <BarChart data={bins}>
                  <CartesianGrid stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="band" stroke="var(--muted-foreground)" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis stroke="var(--muted-foreground)" fontSize={11} tickLine={false} axisLine={false} domain={[0, 100]} unit="%" width={40} />
                  <Tooltip {...tip} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Confidence" fill="var(--gen)" radius={[4, 4, 0, 0]} animationDuration={1200} />
                  <Bar dataKey="Accuracy" fill="var(--primary)" radius={[4, 4, 0, 0]} animationDuration={1400} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        </Reveal>
        <Reveal delay={0.2} className="lg:col-span-2">
          <Panel title="Claim precision by type" hint="Backtested on rows after each cut-off">
            <div className="space-y-4">
              {groups.map((g, i) => (
                <div key={g.group}>
                  <div className="mb-1.5 flex justify-between text-sm">
                    <span className="font-mono">{g.group}</span>
                    <span className="font-mono text-muted-foreground">{g.right}/{g.n} · {pct(g.precision, 1)}</span>
                  </div>
                  <div className="relative h-2 overflow-hidden rounded-full bg-muted">
                    <motion.div className="h-full rounded-full bg-primary" initial={{ width: 0 }} animate={{ width: `${g.precision * 100}%` }} transition={{ duration: 1.1, ease, delay: 0.3 + i * 0.1 }} />
                    <div className="absolute top-0 h-full w-0.5 bg-gen" style={{ left: `${g.confidence * 100}%` }} title="stated confidence" />
                  </div>
                </div>
              ))}
              <p className="text-xs text-muted-foreground"><span className="mr-1 inline-block h-2 w-0.5 bg-gen align-middle" />stated confidence</p>
            </div>
          </Panel>
        </Reveal>
      </div>
      <Reveal delay={0.25} className="mt-4">
        <Panel title="Weak spots" hint="Where the team is still working">
          <div className="grid gap-3 md:grid-cols-3 text-sm">
            <div className="rounded-lg bg-surface p-4"><div className="font-mono text-verdict-false">false @ 0.5–0.8</div><p className="mt-1 text-muted-foreground">{pct(falseMid.accuracy)} right over {falseMid.n} answers — lies are hard to call with mid confidence.</p></div>
            <div className="rounded-lg bg-surface p-4"><div className="font-mono text-verdict-true">true @ 0.5–0.6</div><p className="mt-1 text-muted-foreground">{pct(trueLow.accuracy)} right over {trueLow.n} answers — a candidate band for 'unsure'.</p></div>
            <div className="rounded-lg bg-surface p-4"><div className="font-mono text-verdict-unsure">unsure</div><p className="mt-1 text-muted-foreground">Never predicted yet; a team decision once scoring is known.</p></div>
          </div>
        </Panel>
      </Reveal>
    </>
  );
}
