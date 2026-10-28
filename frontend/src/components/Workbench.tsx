"use client";

import { useEffect, useMemo, useState } from "react";
import type { ApiError, InputRow, Label, Prediction, PredictCsvResponse, PredictResponse } from "@/lib/types";
import PredictionDetail from "./PredictionDetail";
import { ConfidenceBar, VerdictBadge } from "./Verdict";

type Health = { state: "checking" } | { state: "ready"; demo: boolean } | { state: "down"; error: string };

interface RunResult {
  rows: InputRow[];
  predictions: Prediction[];
  demo: boolean;
  source: string;
}

const PREVIEW_BYTES = 64 * 1024;
const PREVIEW_LINES = 8;

export default function Workbench() {
  const [health, setHealth] = useState<Health>({ state: "checking" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<RunResult | null>(null);

  const checkHealth = async () => {
    setHealth({ state: "checking" });
    try {
      const res = await fetch("/api/health", { cache: "no-store" });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
      setHealth({ state: "ready", demo: Boolean(body.demo_mode) });
    } catch (e) {
      setHealth({ state: "down", error: e instanceof Error ? e.message : String(e) });
    }
  };
  useEffect(() => {
    checkHealth();
  }, []);

  const run = async (call: () => Promise<Response>, source: string) => {
    setBusy(true);
    setError(null);
    try {
      const res = await call();
      const body = await res.json().catch(() => ({ error: `HTTP ${res.status}: response is not JSON.` }));
      if (!res.ok) {
        setError(body as ApiError);
        setResult(null);
        return;
      }
      const data = body as PredictResponse & Partial<PredictCsvResponse>;
      const rows = data.rows ?? [];
      setResult({ rows, predictions: data.predictions, demo: data.demo_mode, source });
    } catch (e) {
      setError({ error: "The request failed.", detail: e instanceof Error ? e.message : String(e) });
      setResult(null);
    } finally {
      setBusy(false);
    }
  };

  const runCsv = (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    run(() => fetch("/api/predict/csv", { method: "POST", body: fd }), file.name);
  };

  return (
    <div className="space-y-6">
      <ModeBanner health={health} retry={checkHealth} />

      <section className="rounded-2xl border border-line bg-surface p-5">
        <h2 className="mb-4 font-semibold">Upload CSV</h2>
        <CsvInput busy={busy} onRun={runCsv} demo={health.state === "ready" && health.demo} />
      </section>

      {busy && (
        <div className="flex items-center gap-3 rounded-2xl border border-line bg-surface p-5 text-sm text-muted">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-cls" />
          Running the engine…
        </div>
      )}

      {error && !busy && (
        <div role="alert" className="rounded-2xl border border-bad/40 bg-bad-soft p-5 text-sm">
          <p className="font-semibold text-bad">{error.error}</p>
          {error.detail && <p className="mt-1 whitespace-pre-wrap font-mono text-xs">{error.detail}</p>}
          <p className="mt-2 text-xs text-muted">No verdicts are shown when the engine fails.</p>
        </div>
      )}

      {result && !busy && <Results result={result} />}
    </div>
  );
}

function ModeBanner({ health, retry }: { health: Health; retry: () => void }) {
  if (health.state === "checking")
    return <div className="rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-muted">Checking the engine API…</div>;
  if (health.state === "down")
    return (
      <div className="flex items-center justify-between gap-4 rounded-xl border border-bad/40 bg-bad-soft px-4 py-2.5 text-sm">
        <span>
          <strong className="text-bad">Engine API not reachable.</strong> {health.error}
        </span>
        <button onClick={retry} className="shrink-0 rounded-md border border-line bg-surface px-2.5 py-1 text-xs">
          Retry
        </button>
      </div>
    );
  if (health.demo)
    return (
      <div className="rounded-xl border border-warn/50 bg-warn-soft px-4 py-2.5 text-sm">
        <strong className="text-warn">Demo mode — simulated results</strong>
        <span className="text-muted"> (mod demonstrativ — rezultate simulate). The engine is not connected; every verdict below is a fixed fixture.</span>
      </div>
    );
  return (
    <div className="flex items-center gap-2 rounded-xl border border-ui/40 bg-ui-soft px-4 py-2.5 text-sm">
      <span className="h-2 w-2 rounded-full bg-ui" />
      <span>
        <strong>Live engine connected.</strong> <span className="text-muted">Verdicts come from the Python engine through the API.</span>
      </span>
    </div>
  );
}

function CsvInput({ busy, onRun, demo }: { busy: boolean; onRun: (f: File) => void; demo: boolean }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string[]>([]);
  const [drag, setDrag] = useState(false);

  const pick = async (f: File | undefined) => {
    if (!f) return;
    setFile(f);
    // Raw lines for a glance only; the API owns CSV parsing.
    const head = await f.slice(0, PREVIEW_BYTES).text();
    setPreview(head.split(/\r?\n/).slice(0, PREVIEW_LINES));
  };

  return (
    <div className="space-y-4">
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          pick(e.dataTransfer.files[0]);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center text-sm transition-colors ${
          drag ? "border-cls bg-cls-soft" : "border-line hover:border-muted"
        }`}
      >
        <input type="file" accept=".csv,text/csv" className="sr-only" onChange={(e) => pick(e.target.files?.[0])} />
        {file ? (
          <>
            <span className="font-medium">{file.name}</span>
            <span className="text-xs text-muted">{(file.size / 1024).toFixed(1)} KB · click or drop to replace</span>
          </>
        ) : (
          <>
            <span className="font-medium">Drop a CSV here, or click to choose</span>
            <span className="text-xs text-muted">
              Columns <code className="font-mono">id,text,date,label</code> — rows with an empty label are checked
            </span>
          </>
        )}
      </label>

      {preview.length > 0 && (
        <div>
          <p className="mb-1 text-xs text-muted">First lines of the file, unparsed</p>
          <pre className="max-h-48 overflow-auto rounded-lg bg-bg p-3 font-mono text-xs leading-relaxed">{preview.join("\n")}</pre>
        </div>
      )}

      {demo && file && (
        <p className="text-xs text-warn">Demo mode: the file is not parsed; the fixture rows are shown instead.</p>
      )}

      <button
        disabled={!file || busy}
        onClick={() => file && onRun(file)}
        className="rounded-lg bg-fg px-4 py-2 text-sm font-medium text-bg disabled:opacity-40"
      >
        Run the engine
      </button>
    </div>
  );
}

type Filter = "all" | Label;

function Results({ result }: { result: RunResult }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<string | null>(null);

  const rowsById = useMemo(() => new Map(result.rows.map((r) => [r.id, r])), [result.rows]);
  const predById = useMemo(() => new Map(result.predictions.map((p) => [p.id, p])), [result.predictions]);
  const targets = useMemo(() => result.rows.filter((r) => r.label === ""), [result.rows]);
  const labelled = result.rows.length - targets.length;

  const counts = useMemo(() => {
    const c = { true: 0, false: 0, unsure: 0, missing: 0 };
    for (const r of targets) {
      const p = predById.get(r.id);
      if (p) c[p.label]++;
      else c.missing++;
    }
    return c;
  }, [targets, predById]);

  const shown = targets.filter((r) => filter === "all" || predById.get(r.id)?.label === filter);
  const current = selected ?? shown[0]?.id ?? null;
  const currentRow = current ? rowsById.get(current) : undefined;
  const currentPred = current ? predById.get(current) : undefined;

  return (
    <section className="rounded-2xl border border-line bg-surface">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
        <div>
          <h2 className="font-semibold">
            Results {result.demo && <span className="ml-1 rounded bg-warn-soft px-1.5 py-0.5 text-xs font-medium text-warn">simulated</span>}
          </h2>
          <p className="text-xs text-muted">
            {result.source} · {targets.length} checked{labelled > 0 && ` · ${labelled} labelled rows used as context`}
            {counts.missing > 0 && <span className="text-warn"> · {counts.missing} without a prediction (count as unsure)</span>}
          </p>
        </div>
        <div className="flex gap-1 text-xs">
          {(["all", "true", "false", "unsure"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-full border px-3 py-1 ${filter === f ? "border-fg bg-fg text-bg" : "border-line text-muted"}`}
            >
              {f} <span className="tabular-nums opacity-70">{f === "all" ? targets.length : counts[f]}</span>
            </button>
          ))}
        </div>
      </header>

      {targets.length === 0 ? (
        <p className="p-5 text-sm text-muted">The input has no rows with an empty label, so there is nothing to check.</p>
      ) : (
        <div className="grid lg:grid-cols-[minmax(0,1fr)_420px]">
          <div className="max-h-[640px] overflow-auto border-line lg:border-r">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface text-left text-xs text-muted">
                <tr>
                  <th className="px-5 py-2 font-normal">Row</th>
                  <th className="px-2 py-2 font-normal">Date</th>
                  <th className="px-2 py-2 font-normal">Verdict</th>
                  <th className="px-5 py-2 font-normal">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((r) => {
                  const p = predById.get(r.id);
                  const active = r.id === current;
                  return (
                    <tr
                      key={r.id}
                      onClick={() => setSelected(r.id)}
                      className={`cursor-pointer border-t border-line align-top ${active ? "bg-cls-soft" : "hover:bg-bg"}`}
                    >
                      <td className="px-5 py-2.5">
                        <div className="font-mono text-[11px] text-muted">{r.id}</div>
                        <div className="line-clamp-2">{r.text}</div>
                      </td>
                      <td className="whitespace-nowrap px-2 py-2.5 text-xs tabular-nums text-muted">{r.date}</td>
                      <td className="px-2 py-2.5">{p ? <VerdictBadge label={p.label} /> : <span className="text-xs text-muted">none</span>}</td>
                      <td className="px-5 py-2.5">{p && <ConfidenceBar value={p.confidence} />}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <aside className="border-t border-line p-5 lg:border-t-0">
            {currentRow && currentPred ? (
              <PredictionDetail key={currentRow.id} row={currentRow} prediction={currentPred} rowsById={rowsById} />
            ) : currentRow ? (
              <p className="text-sm text-muted">The engine returned no prediction for {currentRow.id}.</p>
            ) : (
              <p className="text-sm text-muted">No rows match this filter.</p>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}
