"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { EngineError, getMetrics, type EngineFailure } from "@/lib/api";
import type { ClaimCalibration, LabelCalibration, MetricsResponse } from "@/lib/types";
import { CalibrationBars, CalibrationTable, TOLERANCE, isCalibrated, type CalibrationRow } from "./CalibrationBars";

const band = (from: number, to: number) => `${Math.round(from * 100)}–${Math.round(to * 100)}%`;

function labelRows(m: LabelCalibration): CalibrationRow[] {
  return m.bins.map((b) => ({ name: `${b.label} ${band(b.from, b.to)}`, said: b.confidence, right: b.accuracy, n: b.n }));
}

function claimRows(m: ClaimCalibration): CalibrationRow[] {
  return m.groups.map((g) => ({ name: g.group.replace("_", " "), said: g.confidence, right: g.precision, n: g.n }));
}

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
  const claims = data.claims ? claimRows(data.claims) : null;

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
        <Tile label="Claims in calibrated types" value={claims ? share(claims) : "—"} note={`right within ±${TOLERANCE * 100} points of what we said`} />
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
            ? `Backtest: claims built from the rows before each cut-off (${data.claims.cutoffs.join(", ")}), checked against the rows after it.`
            : undefined
        }
        missing="The API has no claim backtest yet (reports/claims_calibration.json)."
        rows={claims}
        unit="Claims"
      />

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

function Section({ title, sub, missing, rows, unit }: {
  title: string;
  sub?: string;
  missing: string;
  rows: CalibrationRow[] | null;
  unit: string;
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
    </section>
  );
}
