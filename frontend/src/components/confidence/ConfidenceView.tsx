"use client";

import { useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { EngineError, getMetrics, type EngineFailure } from "@/lib/api";
import type { ClaimCalibration, ClaimGroup, ControlReport, LabelCalibration, MetricsResponse, ShiftScenario } from "@/lib/types";
import { CalibrationBars, CalibrationTable, TOLERANCE, isCalibrated, type CalibrationRow } from "./CalibrationBars";

const band = (from: number, to: number) => `${Math.round(from * 100)}–${Math.round(to * 100)}%`;

function labelRows(m: LabelCalibration): CalibrationRow[] {
  return m.bins.map((b) => ({ name: `${b.label} ${band(b.from, b.to)}`, said: b.confidence, right: b.accuracy, n: b.n }));
}

// A claim type counts as checked only when the strict judge (rows the generator never saw)
// judged enough of it; the full judge alone is partly circular and always says ~100%.
const MIN_STRICT = 20;
const groupName = (g: ClaimGroup) => g.group.replace("_", " ");
// Older reports (the fixture) have no strict judge: their full-judge numbers are shown as they are.
const legacy = (g: ClaimGroup) => g.strict_n === undefined;
const strictlyChecked = (g: ClaimGroup) => legacy(g) || ((g.strict_n ?? 0) >= MIN_STRICT && g.strict_precision != null);

function claimRows(m: ClaimCalibration): CalibrationRow[] {
  return m.groups.filter(strictlyChecked).map((g) =>
    legacy(g)
      ? { name: groupName(g), said: g.confidence, right: g.precision, n: g.n }
      : { name: groupName(g), said: g.confidence, right: g.strict_precision as number, n: g.strict_n as number },
  );
}

const pct = (x: number) => `${Math.round(x * 100)}%`;
const fixed = (x: number | null | undefined, d = 3) => (x == null ? "—" : x.toFixed(d));

// How many rows/claims sit in bands that meet the plan's ±5-point limit.
function share(rows: CalibrationRow[]): string {
  const total = rows.reduce((a, r) => a + r.n, 0);
  const ok = rows.filter((r) => isCalibrated(r.said, r.right)).reduce((a, r) => a + r.n, 0);
  return total ? `${Math.round((ok / total) * 100)}%` : "—";
}

// "We said X → we were right Y" for labels and for each claim type, from GET /metrics.
export function ConfidenceView() {
  const [data, setData] = useState<MetricsResponse | null>(null);
  const [error, setError] = useState<EngineFailure | null>(null);

  useEffect(() => {
    getMetrics().then(setData, (e) =>
      setError({ message: e instanceof Error ? e.message : "The API failed.", detail: e instanceof EngineError ? e.detail : undefined }),
    );
  }, []);

  if (error)
    return (
      <div role="alert" className="card-soft flex gap-3 bg-bad-soft p-5 text-bad">
        <AlertTriangle className="mt-0.5 size-5 shrink-0" />
        <div>
          <p className="font-semibold">The measurements could not be loaded: {error.message}</p>
          {error.detail && <p className="mt-1 break-words font-mono text-xs">{error.detail}</p>}
          <p className="mt-2 text-xs opacity-80">No numbers are shown without a measurement behind them.</p>
        </div>
      </div>
    );
  if (!data)
    return (
      <p className="card-soft flex items-center gap-2 p-5 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> Loading the measurements…
      </p>
    );

  const labels = data.labels ? labelRows(data.labels) : null;
  const checked = data.claims ? claimRows(data.claims) : null;
  const claims = checked && checked.length ? checked : null;
  const capped = data.claims ? data.claims.groups.filter((g) => !strictlyChecked(g)) : [];
  const cap = data.claims?.unverified_cap ?? 0.95;

  return (
    <div className="space-y-6">
      {data.simulated && (
        <div className="card-soft bg-warn-soft p-4 text-sm text-warn">
          <strong>Simulated measurements.</strong> These numbers come from this frontend&apos;s fixture, not from the API&apos;s
          GET /metrics: the counts and accuracies are the team&apos;s measurements from the plan, and each confidence is the
          midpoint of the reported range.
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <Tile
          label="Label calibration error (ECE)"
          value={
            data.labels?.ece_after != null
              ? `${data.labels.ece_after.toFixed(2)}`
              : data.labels?.ece_before != null
                ? data.labels.ece_before.toFixed(2)
                : "—"
          }
          note={
            data.labels?.ece_before != null && data.labels.ece_after != null
              ? `was ${data.labels.ece_before.toFixed(2)} before calibration; 0 is perfect`
              : "0 is perfect"
          }
        />
        <Tile label="Labels in calibrated bands" value={labels ? share(labels) : "—"} note={`right within ±${TOLERANCE * 100} points of what we said`} />
        <Tile
          label="Checkable claims in calibrated types"
          value={claims ? share(claims) : "—"}
          note={`a share of claims, not a confidence: of the types unseen rows can check, right within ±${TOLERANCE * 100} points of what we said`}
        />
      </div>

      <Section
        title="Labels: we said → we were right"
        sub={
          data.labels
            ? `Rows the model never learned from (${data.labels.fitted_on}); calibration: ${data.labels.method}.`
            : undefined
        }
        missing="The API has no label calibration yet (eval/calibration_labels.json)."
        rows={labels}
        unit="Rows"
      />
      <Section
        title="Claims by type: we said → they were true"
        sub={
          data.claims
            ? `Backtest: claims built from the practice rows before each cut-off (${data.claims.cutoffs.join(", ")}), checked only against the rows after it, which the generator never saw. Types those rows cannot check are capped at ${cap}.`
            : undefined
        }
        missing={
          data.claims
            ? "No claim type could be checked on unseen rows."
            : "The API has no claim backtest yet (reports/claims_calibration.json)."
        }
        rows={claims}
        unit="Claims"
        footer={
          capped.length > 0 && (
            <ul className="mt-4 space-y-1 text-sm text-muted-foreground">
              {capped.map((g) => (
                <li key={g.group}>
                  <span className="font-semibold text-heading">{groupName(g)}</span>: confidence {g.confidence}, capped at {cap}:
                  unseen rows can&apos;t check it ({g.n.toLocaleString("en-US")} backtested on all practice rows, which also built them).
                </li>
              ))}
            </ul>
          )
        }
      />

      <ShiftSection shift={data.shift} />
      <ControlsCard controls={data.controls} />

      <p className="text-xs text-muted-foreground">
        The practice data is about 10% of the final input, so every number here is an estimate from that 10%.
      </p>
    </div>
  );
}

function Tile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="card-soft p-5">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-2 text-3xl font-bold tabular-nums text-heading">{value}</p>
      <p className="mt-2 text-xs text-muted-foreground">{note}</p>
    </div>
  );
}

function Section({ title, sub, missing, rows, unit, footer }: {
  title: string;
  sub?: string;
  missing: string;
  rows: CalibrationRow[] | null;
  unit: string;
  footer?: ReactNode;
}) {
  return (
    <section className="card-soft p-5 sm:p-6">
      <h2 className="text-lg font-bold">{title}</h2>
      {rows ? (
        <>
          {sub && <p className="mt-1 text-sm text-muted-foreground">{sub}</p>}
          <div className="mt-4">
            <CalibrationBars rows={rows} />
          </div>
          <CalibrationTable rows={rows} unit={unit} />
        </>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">Not measured yet. {missing}</p>
      )}
      {footer}
    </section>
  );
}

// "Does our confidence hold when the data shifts?" (scripts/shift_test.py)
function ShiftSection({ shift }: { shift: ShiftScenario[] | null }) {
  return (
    <section className="card-soft p-5 sm:p-6">
      <h2 className="text-lg font-bold">Shift test: when the data changes</h2>
      {shift && shift.length ? (
        <>
          <p className="mt-1 text-sm text-muted-foreground">
            In each scenario about 20% of the practice data is unseen. The models are trained only on the rest, then the run
            is replayed with the confidence control, which can only lower confidence.
          </p>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="text-xs text-muted-foreground">
                <tr>
                  <th className="pb-2 font-medium">Unseen part</th>
                  <th className="pb-2 text-right font-medium">Rows</th>
                  <th className="pb-2 text-right font-medium">Right</th>
                  <th className="pb-2 text-right font-medium">Always &quot;true&quot;</th>
                  <th className="pb-2 text-right font-medium">We said → after control</th>
                  <th className="pb-2 text-right font-medium">ECE → after control</th>
                </tr>
              </thead>
              <tbody>
                {shift.map((s) => {
                  const below = s.unseen_before.right < s.always_true;
                  return (
                    <tr key={s.scenario} className="border-t">
                      <td className="py-2 pr-4 font-medium text-heading">{s.scenario}</td>
                      <td className="py-2 text-right tabular-nums text-muted-foreground">{s.unseen_before.n}</td>
                      <td className="py-2 text-right font-semibold tabular-nums text-heading">
                        {pct(s.unseen_before.right)}
                        {below && (
                          <span className="ml-2 inline-flex rounded-full bg-bad-soft px-2 py-0.5 text-xs font-semibold text-bad">
                            below always &quot;true&quot;
                          </span>
                        )}
                      </td>
                      <td className="py-2 text-right tabular-nums">{pct(s.always_true)}</td>
                      <td className="py-2 text-right tabular-nums">
                        {fixed(s.unseen_before.said)} → {fixed(s.unseen_after.said)}
                      </td>
                      <td className="py-2 text-right tabular-nums">
                        {fixed(s.unseen_before.ece)} → {fixed(s.unseen_after.ece)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            ECE: the gap between what we said and how often we were right; 0 is perfect.
          </p>
        </>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">Not measured yet. The API has no shift test (reports/shift_test.json).</p>
      )}
    </section>
  );
}

// The run-time confidence control, as it behaves on the practice data (scripts/train_control.py).
function ControlsCard({ controls }: { controls: ControlReport | null }) {
  return (
    <section className="card-soft p-5 sm:p-6">
      <h2 className="text-lg font-bold">Run-time controls</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        In the real run a control model that never saw {controls ? controls.control_rows : "a group of"} practice rows labels
        them beside the new input. Where it was over-confident, every answer of that label is lowered to match; confidence is
        never raised. Input rows the engine is sure of can veto a claim they contradict, and lower its type&apos;s confidence.
      </p>
      {controls && controls.accuracy != null ? (
        <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-4">
          <Fact label="Control answers" value={controls.control_answers.toLocaleString("en-US")} />
          <Fact label="Right" value={pct(controls.accuracy)} />
          <Fact label="We said" value={fixed(controls.said)} />
          <Fact
            label="Lowered by"
            value={
              !controls.factors
                ? "—"
                : Object.values(controls.factors).every((k) => k === 1)
                  ? "nothing"
                  : Object.entries(controls.factors)
                      .filter(([, k]) => k !== 1)
                      .map(([label, k]) => `${label} ×${k}`)
                      .join(", ")
            }
          />
        </dl>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">
          Not measured yet. {controls?.note ?? "The API has no control report (reports/controls.json)."}
        </p>
      )}
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-lg font-bold tabular-nums text-heading">{value}</dd>
    </div>
  );
}
