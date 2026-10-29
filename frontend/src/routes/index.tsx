import { createFileRoute, Link } from "@tanstack/react-router";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowUpRight, CheckCircle2, Clock, Sparkles, Target } from "lucide-react";
import { motion } from "motion/react";
import practice from "@/data/practice.json";
import { Counter, Panel, PageHeader, Reveal, ease } from "@/components/arena/ui";
import { ArchDiagram } from "@/components/arena/ArchDiagram";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Overview — Hype Arena" },
      { name: "description", content: "Accuracy, calibration and claim output of the Hype Arena fact-checking system at a glance." },
      { property: "og:title", content: "Overview — Hype Arena" },
      { property: "og:description", content: "Accuracy, calibration and claim output of the Hype Arena fact-checking system." },
    ],
  }),
  component: Overview,
});

const tip = { contentStyle: { background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }, cursor: { fill: "var(--accent)", opacity: 0.4 } };

// Measured by the batch run on practice (scripts/check.sh: 380 hidden rows, 1,000 claims).
const KPIS = [
  { label: "Hidden rows labelled right", value: 89.5, d: 1, suffix: "%", sub: "340 / 380 · always 'true' 85%", icon: Target },
  { label: "Answers at 0.9+ confidence", value: 96.7, d: 1, suffix: "%", sub: "207 of 214 answers right", icon: CheckCircle2 },
  { label: "Claims generated", value: 1000, d: 0, suffix: "", sub: "mean confidence 0.959", icon: Sparkles },
  { label: "Full run, 20k rows", value: 131, d: 0, suffix: "s", sub: "synthetic input · of a 30 min budget", icon: Clock },
];

const CLAIM_MIX = [
  { name: "compare", value: 430, fill: "var(--chart-1)" },
  { name: "change", value: 317, fill: "var(--chart-2)" },
  { name: "at_event", value: 247, fill: "var(--chart-4)" },
  { name: "fact", value: 4, fill: "var(--chart-3)" },
  { name: "relation", value: 2, fill: "var(--chart-5)" },
];

function Overview() {
  const labels = practice.labels as Record<string, number>;
  return (
    <>
      <PageHeader eyebrow="Git Happens · NEXXT AI Hackathon" title="System overview">
        <Link to="/run" className="group inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground glow transition hover:brightness-110">
          Run on new rows <ArrowUpRight className="h-4 w-4 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
        </Link>
      </PageHeader>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {KPIS.map((k, i) => (
          <Reveal key={k.label} delay={0.05 * i}>
            <motion.div whileHover={{ y: -3 }} transition={{ duration: 0.25, ease }} className="panel group relative overflow-hidden p-5">
              <div className="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-primary/10 blur-2xl transition-opacity group-hover:opacity-100 opacity-40" />
              <div className="flex items-center justify-between">
                <span className="eyebrow">{k.label}</span>
                <k.icon className="h-4 w-4 text-primary" />
              </div>
              <div className="mt-3 text-4xl font-semibold tracking-tight">
                <Counter value={k.value} decimals={k.d} suffix={k.suffix} />
              </div>
              <div className="mt-1 text-xs text-muted-foreground">{k.sub}</div>
            </motion.div>
          </Reveal>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Reveal delay={0.2} className="lg:col-span-2">
          <Panel title="Practice universe over time" hint={`${practice.total.toLocaleString()} labelled sentences by month`}>
            <div className="h-64">
              <ResponsiveContainer>
                <AreaChart data={practice.months}>
                  <defs>
                    {["t", "f", "u"].map((k, i) => (
                      <linearGradient key={k} id={`g${k}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={["var(--verdict-true)", "var(--verdict-false)", "var(--verdict-unsure)"][i]!} stopOpacity={0.4} />
                        <stop offset="100%" stopColor={["var(--verdict-true)", "var(--verdict-false)", "var(--verdict-unsure)"][i]!} stopOpacity={0} />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid stroke="var(--border)" vertical={false} />
                  <XAxis dataKey="month" stroke="var(--muted-foreground)" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="var(--muted-foreground)" fontSize={11} tickLine={false} axisLine={false} width={32} />
                  <Tooltip {...tip} />
                  <Area type="monotone" dataKey="true" stroke="var(--verdict-true)" fill="url(#gt)" strokeWidth={2} animationDuration={1400} />
                  <Area type="monotone" dataKey="false" stroke="var(--verdict-false)" fill="url(#gf)" strokeWidth={2} animationDuration={1400} />
                  <Area type="monotone" dataKey="unsure" stroke="var(--verdict-unsure)" fill="url(#gu)" strokeWidth={2} animationDuration={1400} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        </Reveal>
        <Reveal delay={0.25}>
          <Panel title="Label mix" hint="Practice ground truth">
            <div className="space-y-4">
              {(["true", "false", "unsure"] as const).map((l, i) => {
                const share = (labels[l] ?? 0) / practice.total;
                return (
                  <div key={l}>
                    <div className="mb-1.5 flex justify-between text-sm">
                      <span className="capitalize">{l}</span>
                      <span className="font-mono text-muted-foreground">{labels[l]} · {(share * 100).toFixed(1)}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                      <motion.div
                        className={["bg-verdict-true", "bg-verdict-false", "bg-verdict-unsure"][i] + " h-full rounded-full"}
                        initial={{ width: 0 }} animate={{ width: `${share * 100}%` }}
                        transition={{ duration: 1.2, ease, delay: 0.4 + i * 0.1 }}
                      />
                    </div>
                  </div>
                );
              })}
              <div className="rounded-lg border border-border bg-surface p-3 text-xs text-muted-foreground">
                Lies caught: <span className="text-foreground">33 of 49</span> hidden false rows · true rows called false: <span className="text-foreground">17</span>
              </div>
            </div>
          </Panel>
        </Reveal>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Reveal delay={0.3} className="lg:col-span-2">
          <Panel title="Architecture" hint="Classification (blue) and generation (teal) flows" action={<Link to="/architecture" className="text-xs text-primary hover:underline">Replay →</Link>}>
            <ArchDiagram />
          </Panel>
        </Reveal>
        <Reveal delay={0.35}>
          <Panel title="Claim mix" hint="1,000 new claims, every one true">
            <div className="relative h-48">
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={CLAIM_MIX} dataKey="value" innerRadius={55} outerRadius={80} paddingAngle={2} stroke="none" animationDuration={1200}>
                    {CLAIM_MIX.map((c) => <Cell key={c.name} fill={c.fill} />)}
                  </Pie>
                  <Tooltip {...tip} />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
                <div><div className="text-2xl font-semibold">1,000</div><div className="eyebrow">claims</div></div>
              </div>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
              {CLAIM_MIX.map((c) => (
                <div key={c.name} className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-sm" style={{ background: c.fill }} />
                  <span className="text-muted-foreground">{c.name}</span>
                  <span className="ml-auto font-mono">{c.value}</span>
                </div>
              ))}
            </div>
          </Panel>
        </Reveal>
      </div>

      <Reveal delay={0.4} className="mt-4">
        <Panel title="Most-cited attributes" hint="Facts stated across the practice rows">
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={practice.attributes.map(([name, n]) => ({ name, n }))} layout="vertical" margin={{ left: 40 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" stroke="var(--muted-foreground)" fontSize={11} tickLine={false} axisLine={false} width={110} />
                <Tooltip {...tip} />
                <Bar dataKey="n" fill="var(--primary)" radius={[0, 4, 4, 0]} animationDuration={1200} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </Reveal>
    </>
  );
}
