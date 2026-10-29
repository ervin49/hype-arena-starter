import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { motion } from "motion/react";
import fixture from "@/data/metrics.json";
import {
  api,
  pct,
  type ClaimGroup,
  type ControlReport,
  type LabelBin,
  type MetricsResponse,
  type ShiftScenario,
} from "@/lib/arena";
import { Counter, PageHeader, Panel, Reveal, ease } from "@/components/arena/ui";

export const Route = createFileRoute("/confidence")({
  head: () => ({
    meta: [
      { title: "Confidence — Hype Arena" },
      {
        name: "description",
        content: "Calibration of label and claim confidence, measured out of fold.",
      },
      { property: "og:title", content: "Confidence — Hype Arena" },
      { property: "og:description", content: "How well Hype Arena's confidence matches reality." },
    ],
  }),
  component: Conf,
});

const tip = {
  contentStyle: {
    background: "var(--popover)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    fontSize: 12,
  },
  cursor: { fill: "var(--accent)", opacity: 0.4 },
};

// A claim type counts as measured only when the strict judge (rows the generator never saw)
// judged enough of it. The full judge checks claims against the rows that built them, so it
// says ~100% for every type and is never shown as precision.
const MIN_STRICT = 20;
const measured = (g: ClaimGroup) => (g.strict_n ?? 0) >= MIN_STRICT && g.strict_precision != null;
const fixed = (x: number | null | undefined, d = 3) => (x == null ? "—" : x.toFixed(d));

// Accuracy of the answers with this label whose confidence falls in [from, to), pooled over bins.
function pooled(bins: LabelBin[], label: string, from: number, to: number) {
  const sel = bins.filter((b) => b.label === label && b.from >= from && b.to <= to);
  const n = sel.reduce((s, b) => s + b.n, 0);
  return { n, accuracy: n ? sel.reduce((s, b) => s + b.accuracy * b.n, 0) / n : null };
}

function Conf() {
  const q = useQuery({
    queryKey: ["metrics"],
    queryFn: api.metrics,
    retry: false,
    enabled: typeof window !== "undefined",
  });
  // The snapshot is used only when the API cannot be reached, and says so.
  const simulated = !q.data;
  const data = (q.data ?? fixture) as MetricsResponse;
  const labels = data.labels;
  const groups = data.claims?.groups ?? [];
  const checked = groups.filter(measured);
  const capped = groups.filter((g) => !measured(g));
  const cap = data.claims?.unverified_cap ?? 0.95;
  const bins = (labels?.bins ?? []).map((b) => ({
    band: `${b.label} ${b.from}–${b.to}`,
    Accuracy: +(b.accuracy * 100).toFixed(1),
    Confidence: +(b.confidence * 100).toFixed(1),
    n: b.n,
  }));
  const falseMid = pooled(labels?.bins ?? [], "false", 0.5, 0.8);
  const trueLow = pooled(labels?.bins ?? [], "true", 0.5, 0.6);

  return (
    <>
      <PageHeader eyebrow="GET /metrics" title="Confidence & calibration">
        {simulated && (
          <span className="rounded-full border border-verdict-unsure/30 bg-verdict-unsure/10 px-3 py-1 font-mono text-xs text-verdict-unsure">
            fixture · engine offline
          </span>
        )}
      </PageHeader>
      <div className="grid gap-4 md:grid-cols-3">
        <Reveal>
          <div className="panel p-5">
            <div className="eyebrow">ECE before calibration</div>
            <div className="mt-2 text-4xl font-semibold">
              {labels ? <Counter value={labels.ece_before} decimals={3} /> : "—"}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">lower is better</div>
          </div>
        </Reveal>
        <Reveal delay={0.05}>
          <div className="panel p-5">
            <div className="eyebrow">ECE after calibration</div>
            <div className="mt-2 text-4xl font-semibold">
              {labels ? <Counter value={labels.ece_after} decimals={3} /> : "—"}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              Platt, cross-fitted; on rows the model never saw
            </div>
          </div>
        </Reveal>
        <Reveal delay={0.1}>
          <div className="panel p-5">
            <div className="eyebrow">Claim types checked on unseen rows</div>
            <div className="mt-2 text-4xl font-semibold tabular-nums">
              {checked.length} of {groups.length}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">the others are capped at {cap}</div>
          </div>
        </Reveal>
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <Reveal delay={0.15} className="lg:col-span-3">
          <Panel
            title="Reliability by confidence band"
            hint="When the engine says 0.9, it should be right ~90% of the time"
          >
            {labels ? (
              <div className="h-72">
                <ResponsiveContainer>
                  <BarChart data={bins}>
                    <CartesianGrid stroke="var(--border)" vertical={false} />
                    <XAxis
                      dataKey="band"
                      stroke="var(--muted-foreground)"
                      fontSize={10}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis
                      stroke="var(--muted-foreground)"
                      fontSize={11}
                      tickLine={false}
                      axisLine={false}
                      domain={[0, 100]}
                      unit="%"
                      width={40}
                    />
                    <Tooltip {...tip} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar
                      dataKey="Confidence"
                      fill="var(--gen)"
                      radius={[4, 4, 0, 0]}
                      animationDuration={1200}
                    />
                    <Bar
                      dataKey="Accuracy"
                      fill="var(--primary)"
                      radius={[4, 4, 0, 0]}
                      animationDuration={1400}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Not measured yet: the API has no label calibration (eval/calibration_labels.json).
              </p>
            )}
          </Panel>
        </Reveal>
        <Reveal delay={0.2} className="lg:col-span-2">
          <Panel
            title="Claim precision by type"
            hint="Checked only on rows dated after each cut-off, which the generator never saw"
          >
            <div className="space-y-4">
              {checked.map((g, i) => (
                <div key={g.group}>
                  <div className="mb-1.5 flex justify-between text-sm">
                    <span className="font-mono">{g.group}</span>
                    <span className="font-mono text-muted-foreground">
                      {g.strict_right}/{g.strict_n} · {pct(g.strict_precision, 1)}
                    </span>
                  </div>
                  <div className="relative h-2 overflow-hidden rounded-full bg-muted">
                    <motion.div
                      className="h-full rounded-full bg-primary"
                      initial={{ width: 0 }}
                      animate={{ width: `${(g.strict_precision ?? 0) * 100}%` }}
                      transition={{ duration: 1.1, ease, delay: 0.3 + i * 0.1 }}
                    />
                    <div
                      className="absolute top-0 h-full w-0.5 bg-gen"
                      style={{ left: `${g.confidence * 100}%` }}
                      title="stated confidence"
                    />
                  </div>
                </div>
              ))}
              {!checked.length && (
                <p className="text-sm text-muted-foreground">
                  No claim type could be checked on unseen rows yet.
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                <span className="mr-1 inline-block h-2 w-0.5 bg-gen align-middle" />
                stated confidence
              </p>
              {capped.length > 0 && (
                <ul className="space-y-1 border-t border-border pt-3 text-xs text-muted-foreground">
                  {capped.map((g) => (
                    <li key={g.group}>
                      <span className="font-mono text-foreground">{g.group}</span>: capped at {cap}:
                      unseen rows can't check this type
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Panel>
        </Reveal>
      </div>
      <Reveal delay={0.25} className="mt-4">
        <ShiftPanel shift={data.shift ?? null} />
      </Reveal>
      <Reveal delay={0.3} className="mt-4">
        <ControlsPanel controls={data.controls ?? null} />
      </Reveal>
      <Reveal delay={0.35} className="mt-4">
        <Panel title="Weak spots" hint="Where the team is still working">
          <div className="grid gap-3 md:grid-cols-3 text-sm">
            <div className="rounded-lg bg-surface p-4">
              <div className="font-mono text-verdict-false">false @ 0.5–0.8</div>
              <p className="mt-1 text-muted-foreground">
                {pct(falseMid.accuracy)} right over {falseMid.n} answers — lies are hard to call
                with mid confidence.
              </p>
            </div>
            <div className="rounded-lg bg-surface p-4">
              <div className="font-mono text-verdict-true">true @ 0.5–0.6</div>
              <p className="mt-1 text-muted-foreground">
                {pct(trueLow.accuracy)} right over {trueLow.n} answers — a candidate band for
                'unsure'.
              </p>
            </div>
            <div className="rounded-lg bg-surface p-4">
              <div className="font-mono text-verdict-unsure">unsure</div>
              <p className="mt-1 text-muted-foreground">
                Never predicted yet; a team decision once scoring is known.
              </p>
            </div>
          </div>
        </Panel>
      </Reveal>
    </>
  );
}

// scripts/shift_test.py: does the confidence hold when the unseen rows differ from the known ones?
function ShiftPanel({ shift }: { shift: ShiftScenario[] | null }) {
  return (
    <Panel
      title="Shift test: when the data changes"
      hint="About 20% of practice unseen per scenario; models trained on the rest, then the run is replayed with the confidence control, which can only lower confidence"
    >
      {shift?.length ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr>
                <th className="pb-2 font-medium">Unseen part</th>
                <th className="pb-2 text-right font-medium">Rows</th>
                <th className="pb-2 text-right font-medium">Right</th>
                <th className="pb-2 text-right font-medium">Always "true"</th>
                <th className="pb-2 text-right font-medium">Said → after control</th>
                <th className="pb-2 text-right font-medium">ECE → after control</th>
              </tr>
            </thead>
            <tbody>
              {shift.map((s) => (
                <tr key={s.scenario} className="border-t border-border">
                  <td className="py-2 pr-4">{s.scenario}</td>
                  <td className="py-2 text-right font-mono text-muted-foreground">
                    {s.unseen_before.n}
                  </td>
                  <td className="py-2 text-right font-mono">
                    {pct(s.unseen_before.right, 1)}
                    {s.unseen_before.right < s.always_true && (
                      <span className="ml-2 rounded-full border border-verdict-false/30 bg-verdict-false/10 px-2 py-0.5 text-[11px] text-verdict-false">
                        below always 'true'
                      </span>
                    )}
                  </td>
                  <td className="py-2 text-right font-mono">{pct(s.always_true, 1)}</td>
                  <td className="py-2 text-right font-mono">
                    {fixed(s.unseen_before.said)} → {fixed(s.unseen_after.said)}
                  </td>
                  <td className="py-2 text-right font-mono">
                    {fixed(s.unseen_before.ece)} → {fixed(s.unseen_after.ece)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-muted-foreground">
            ECE: the gap between what we said and how often we were right; 0 is perfect.
          </p>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Not measured yet: the API has no shift test (reports/shift_test.json).
        </p>
      )}
    </Panel>
  );
}

// arena/controls.py on practice (scripts/train_control.py): a control model that never saw a held-out
// group labels it beside the input; where it was over-confident, that label's confidence is lowered.
function ControlsPanel({ controls }: { controls: ControlReport | null }) {
  const lowered = !controls?.factors
    ? "—"
    : Object.values(controls.factors).every((k) => k === 1)
      ? "nothing"
      : Object.entries(controls.factors)
          .filter(([, k]) => k !== 1)
          .map(([label, k]) => `${label} ×${k}`)
          .join(", ");
  return (
    <Panel
      title="Run-time controls"
      hint={`A control model that never saw ${controls ? controls.control_rows : "a group of"} practice rows labels them beside the input; confidence can only be lowered, never raised`}
    >
      {controls && controls.accuracy != null ? (
        <dl className="grid gap-4 text-sm sm:grid-cols-4">
          {[
            ["Control answers", controls.control_answers.toLocaleString("en-US")],
            ["Right", pct(controls.accuracy, 1)],
            ["Said", fixed(controls.said)],
            ["Lowered by", lowered],
          ].map(([k, v]) => (
            <div key={k}>
              <dt className="eyebrow">{k}</dt>
              <dd className="mt-1 font-mono text-lg">{v}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-sm text-muted-foreground">
          Not measured yet.{" "}
          {controls?.note ?? "The API has no control report (reports/controls.json)."}
        </p>
      )}
    </Panel>
  );
}
