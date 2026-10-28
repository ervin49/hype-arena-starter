import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface CalibrationRow {
  name: string;
  // What we reported (confidence) and how often we were right (accuracy), both 0–1.
  said: number;
  right: number;
  n: number;
}

// Plan's acceptance limit: a band is calibrated when right is within this of said.
export const TOLERANCE = 0.05;

// Gap in whole points, as the table shows it: 1.0 − 0.95 is 0.0500…04 in floating point.
const gapPoints = (said: number, right: number) => Math.round(Math.abs(right - said) * 100);
export const isCalibrated = (said: number, right: number) => gapPoints(said, right) <= TOLERANCE * 100;

const pct = (x: number) => `${Math.round(x * 100)}%`;

// "We said X → we were right Y", one pair of bars per band or claim type.
export function CalibrationBars({ rows }: { rows: CalibrationRow[] }) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-said" />
          We said (confidence)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-primary" />
          We were right (measured)
        </span>
      </div>
      <div className="mt-3 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} barGap={2} barCategoryGap="28%" margin={{ top: 22, left: -12, right: 4 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="4 4" />
            <XAxis dataKey="name" axisLine={false} tickLine={false} interval={0} tick={{ fill: "var(--muted-foreground)", fontSize: 12 }} />
            <YAxis
              domain={[0, 1]}
              ticks={[0, 0.25, 0.5, 0.75, 1]}
              tickFormatter={pct}
              axisLine={false}
              tickLine={false}
              tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
            />
            <Tooltip
              cursor={{ fill: "var(--muted)" }}
              content={({ active, payload }) => {
                const r = active && payload?.[0] ? (payload[0].payload as CalibrationRow) : null;
                if (!r) return null;
                return (
                  <div className="rounded-xl bg-card px-3 py-2 text-xs shadow-soft">
                    <p className="font-semibold text-heading">{r.name}</p>
                    <p className="text-muted-foreground">
                      said {pct(r.said)} → right {pct(r.right)} · {r.n.toLocaleString("en-US")} measured
                    </p>
                  </div>
                );
              }}
            />
            <Bar dataKey="said" name="We said" fill="var(--said)" radius={[4, 4, 0, 0]} maxBarSize={30}>
              <LabelList dataKey="said" position="top" formatter={(v: unknown) => pct(Number(v))} fill="var(--muted-foreground)" fontSize={11} />
            </Bar>
            <Bar dataKey="right" name="We were right" fill="var(--primary)" radius={[4, 4, 0, 0]} maxBarSize={30}>
              <LabelList dataKey="right" position="top" formatter={(v: unknown) => pct(Number(v))} fill="var(--heading)" fontSize={11} fontWeight={600} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// The same numbers as a table, with a plain-word verdict per row.
export function CalibrationTable({ rows, unit }: { rows: CalibrationRow[]; unit: string }) {
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full min-w-[480px] text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr>
            <th className="pb-2 font-medium">Band</th>
            <th className="pb-2 text-right font-medium">{unit}</th>
            <th className="pb-2 text-right font-medium">We said</th>
            <th className="pb-2 text-right font-medium">Right</th>
            <th className="pb-2 pl-4 font-medium">Verdict</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name} className="border-t">
              <td className="py-2 pr-4 font-medium text-heading">{r.name}</td>
              <td className="py-2 text-right tabular-nums text-muted-foreground">{r.n.toLocaleString("en-US")}</td>
              <td className="py-2 text-right tabular-nums">{pct(r.said)}</td>
              <td className="py-2 text-right font-semibold tabular-nums text-heading">{pct(r.right)}</td>
              <td className="py-2 pl-4">
                <GapPill said={r.said} right={r.right} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GapPill({ said, right }: { said: number; right: number }) {
  const points = gapPoints(said, right);
  const [cls, text] =
    isCalibrated(said, right)
      ? ["bg-ok-soft text-ok", "calibrated"]
      : right < said
        ? ["bg-bad-soft text-bad", `over-confident by ${points} pts`]
        : ["bg-warn-soft text-warn", `under-confident by ${points} pts`];
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`}>{text}</span>;
}
