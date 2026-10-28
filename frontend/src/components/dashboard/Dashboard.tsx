"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { EngineError, getHealth, predictCsv } from "@/lib/api";
import { byMonth, computeStats } from "@/lib/format";
import type { PredictCsvResponse } from "@/lib/types";
import { ArchitectureDiagram } from "./ArchitectureDiagram";
import { DetailPanel } from "./DetailPanel";
import { KpiCards } from "./KpiCards";
import { Sidebar } from "./Sidebar";
import { TopBar, type HealthState } from "./TopBar";
import { UploadCard, type EngineFailure } from "./UploadCard";
import { VerdictChart } from "./VerdictChart";
import { VerdictsTable } from "./VerdictsTable";

const EMPTY: PredictCsvResponse = { rows: [], predictions: [], demo_mode: false };

export default function Dashboard() {
  const [health, setHealth] = useState<HealthState>({ state: "checking" });
  const [data, setData] = useState<PredictCsvResponse | null>(null);
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<EngineFailure | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [dark, setDark] = useState(false);

  const checkHealth = useCallback(async () => {
    setHealth({ state: "checking" });
    try {
      const h = await getHealth();
      setHealth({ state: "ready", demo: h.demo_mode });
    } catch (e) {
      setHealth({ state: "down", error: e instanceof Error ? e.message : String(e) });
    }
  }, []);

  useEffect(() => {
    checkHealth();
    setDark(document.documentElement.classList.contains("dark"));
  }, [checkHealth]);

  const toggleDark = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      // Storage may be blocked; the toggle still works for this visit.
    }
  };

  const run = async (file: File) => {
    setLoading(true);
    setError(null);
    try {
      const res = await predictCsv(file);
      setData(res);
      setSource(file.name);
      setSelectedId(null);
    } catch (e) {
      setData(null);
      setSelectedId(null);
      setError({
        message: e instanceof Error ? e.message : "The engine failed.",
        detail: e instanceof EngineError ? e.detail : undefined,
      });
    } finally {
      setLoading(false);
    }
  };

  const resp = data ?? EMPTY;
  const rowsById = useMemo(() => new Map(resp.rows.map((r) => [r.id, r])), [resp]);
  const stats = useMemo(() => computeStats(resp), [resp]);
  const months = useMemo(() => byMonth(resp), [resp]);
  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    return resp.predictions
      .map((pred) => ({ pred, row: rowsById.get(pred.id) }))
      .filter((x): x is { pred: typeof x.pred; row: NonNullable<typeof x.row> } => !!x.row)
      .filter((x) => !q || x.row.text.toLowerCase().includes(q) || x.row.id.toLowerCase().includes(q));
  }, [resp, rowsById, query]);

  const labelled = resp.rows.filter((r) => r.label !== "").length;
  const unlabelled = resp.rows.length - labelled;
  const unchecked = unlabelled - resp.predictions.length;
  // The engine checks only rows with an empty label; a fully labelled file
  // (such as data/practice.csv) has nothing to check.
  const notice =
    data && unlabelled === 0
      ? `All ${resp.rows.length.toLocaleString("en-US")} rows in ${source} already have a label, so there is nothing to check. Leave the label column empty on the rows you want checked.`
      : undefined;
  const emptyText = notice
    ? "Nothing to check: every row in the file is labelled."
    : query.trim()
      ? "No rows match."
      : "No results yet. Upload a CSV and run the engine.";
  const subtitle = data
    ? [
        source,
        `${resp.predictions.length} checked`,
        labelled > 0 ? `${labelled} labelled rows used as context` : "",
        unchecked > 0 ? `${unchecked} without a prediction (count as unsure)` : "",
      ]
        .filter(Boolean)
        .join(" · ")
    : undefined;

  const currentId = selectedId ?? items[0]?.row.id ?? null;
  const sel = currentId ? resp.predictions.find((p) => p.id === currentId) : undefined;

  return (
    <div id="top" className="min-h-screen bg-background">
      <Sidebar dark={dark} onToggleDark={toggleDark} />
      <div className="flex flex-col gap-6 px-4 pb-24 pt-5 sm:px-6 md:pb-8 md:pl-[96px] xl:flex-row">
        <main className="min-w-0 flex-1 space-y-6">
          <TopBar query={query} onQuery={setQuery} health={health} onRetry={checkHealth} />
          <header>
            <p className="text-xs font-semibold uppercase tracking-widest text-primary">Git Happens · QA DNA — Hype or Truth</p>
            <h1 className="mt-1 text-2xl font-bold sm:text-3xl">Temporal Truth Engine</h1>
            <p className="mt-1 text-sm text-muted-foreground">Checks each sentence against what the Hooly universe said on its date</p>
          </header>
          <KpiCards stats={stats} />
          <VerdictChart data={months} />
          <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
            <UploadCard onRun={run} loading={loading} error={error} notice={notice} />
            <VerdictsTable
              items={items}
              selectedId={currentId}
              onSelect={setSelectedId}
              subtitle={subtitle}
              simulated={Boolean(data?.demo_mode)}
              emptyText={emptyText}
            />
          </div>
          <ArchitectureDiagram />
        </main>
        <aside className="w-full shrink-0 xl:sticky xl:top-5 xl:max-h-[calc(100vh-2.5rem)] xl:w-[360px] xl:overflow-y-auto">
          <DetailPanel key={sel?.id} row={sel ? rowsById.get(sel.id) : undefined} pred={sel} rowsById={rowsById} />
        </aside>
      </div>
    </div>
  );
}
