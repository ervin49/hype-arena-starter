import { createFileRoute } from "@tanstack/react-router";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, Download, FileUp, Loader2, Play, Wand2 } from "lucide-react";
import { useRef, useState } from "react";
import fixture from "@/data/predict-csv.json";
import { api, parseCsv, type InputRow, type Label, type Prediction } from "@/lib/arena";
import { downloadCsv, outputCsv } from "@/lib/csv";
import { ArchDiagram, type NodeId } from "@/components/arena/ArchDiagram";
import { ConfBar, Counter, PageHeader, Panel, Reveal, VerdictPill, ease } from "@/components/arena/ui";

export const Route = createFileRoute("/run")({
  head: () => ({
    meta: [
      { title: "Live run — Hype Arena" },
      { name: "description", content: "Upload rows and watch the system label them true, false or unsure with evidence." },
      { property: "og:title", content: "Live run — Hype Arena" },
      { property: "og:description", content: "Upload rows and watch the system label them live." },
    ],
  }),
  component: RunPage,
});

const SAMPLE = ["id,text,date,label", ...fixture.rows.filter((r) => !r.label).map((r) => `${r.id},"${r.text}",${r.date},`)].join("\n");
const STEPS: { title: string; nodes: NodeId[] }[] = [
  { title: "Parsing rows", nodes: ["U", "F"] },
  { title: "Matching lexicon & extracting facts", nodes: ["U", "L", "X", "F"] },
  { title: "Checking facts against the timeline", nodes: ["X", "K", "P", "V"] },
  { title: "Scoring verdicts", nodes: ["V", "C"] },
  { title: "Returning results", nodes: ["C", "F", "O"] },
];

function RunPage() {
  const [csv, setCsv] = useState(SAMPLE);
  const [step, setStep] = useState(-1);
  const [rows, setRows] = useState<InputRow[]>([]);
  const [preds, setPreds] = useState<Prediction[] | null>(null);
  const [mode, setMode] = useState<"live" | "demo" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const running = step >= 0 && step < STEPS.length;

  async function run() {
    setError(null); setPreds(null); setOpen(null);
    let parsed: InputRow[];
    try { parsed = parseCsv(csv); } catch (e) { setError((e as Error).message); return; }
    if (!parsed.length) { setError("No rows found."); return; }
    setRows(parsed);
    const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
    // No fallback: if the engine fails, the error is shown, never stand-in results.
    const call = api.predict(parsed).then(
      (r) => ({ p: r.predictions, m: r.demo_mode ? ("demo" as const) : ("live" as const), err: null }),
      (e: Error) => ({ p: null, m: null, err: e.message }),
    );
    for (let i = 0; i < STEPS.length; i++) { setStep(i); await wait(650); }
    const { p, m, err } = await call;
    if (err) { setStep(-1); setError(err); return; }
    setStep(STEPS.length); setPreds(p); setMode(m);
  }

  const active = step >= 0 && step < STEPS.length ? new Set(STEPS[step]!.nodes) : undefined;
  const counts = { true: 0, false: 0, unsure: 0 } as Record<Label, number>;
  preds?.forEach((p) => counts[p.label]++);
  const byId = Object.fromEntries(rows.map((r) => [r.id, r]));

  return (
    <>
      <PageHeader eyebrow="POST /predict" title="Live run" />
      <div className="grid gap-4 lg:grid-cols-5">
        <Reveal className="lg:col-span-2">
          <Panel title="Input rows" hint="CSV with id, text, date, label — empty label means 'check this'"
            action={
              <div className="flex gap-1">
                <button onClick={() => setCsv(SAMPLE)} className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground" title="Load example"><Wand2 className="h-4 w-4" /></button>
                <button onClick={() => fileRef.current?.click()} className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground" title="Upload CSV"><FileUp className="h-4 w-4" /></button>
                <input ref={fileRef} type="file" accept=".csv" hidden onChange={async (e) => { const f = e.target.files?.[0]; if (f) setCsv(await f.text()); e.target.value = ""; }} />
              </div>
            }>
            <textarea
              value={csv} onChange={(e) => setCsv(e.target.value)} spellCheck={false}
              className="h-72 w-full resize-none rounded-lg border border-input bg-background p-3 font-mono text-xs leading-relaxed outline-none transition focus:ring-2 focus:ring-ring"
            />
            {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
            <button onClick={run} disabled={running}
              className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground glow transition hover:brightness-110 disabled:opacity-60">
              {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {running ? STEPS[step]?.title + "…" : "Run system"}
            </button>
          </Panel>
        </Reveal>
        <Reveal delay={0.1} className="lg:col-span-3">
          <Panel title="Pipeline" hint="Each stage lights up as the rows move through it">
            <ArchDiagram active={active} />
            <div className="mt-4 grid grid-cols-5 gap-2">
              {STEPS.map((s, i) => (
                <div key={s.title}>
                  <div className="h-1 overflow-hidden rounded-full bg-muted">
                    <motion.div className="h-full bg-primary" initial={false}
                      animate={{ width: step > i ? "100%" : step === i ? "60%" : "0%" }} transition={{ duration: 0.6, ease }} />
                  </div>
                  <div className={"mt-1.5 text-[10px] leading-tight " + (step >= i ? "text-foreground" : "text-muted-foreground")}>{s.title}</div>
                </div>
              ))}
            </div>
          </Panel>
        </Reveal>
      </div>

      <AnimatePresence>
        {preds && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.5, ease }} className="mt-4">
            {mode === "demo" && (
              <div className="mb-4 rounded-lg border border-verdict-unsure/30 bg-verdict-unsure/10 px-4 py-2.5 text-xs text-verdict-unsure">
                The API runs in demo mode (ARENA_DEMO=1): these labels come from its synthetic demo engine, not the real model.
              </div>
            )}
            <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
              {[["Checked", preds.length], ["True", counts.true], ["False", counts.false], ["Unsure", counts.unsure]].map(([k, v]) => (
                <div key={k} className="panel p-4">
                  <div className="eyebrow">{k}</div>
                  <div className="mt-1 text-2xl font-semibold"><Counter value={v as number} /></div>
                </div>
              ))}
            </div>
            <Panel title="Verdicts" hint={mode === "live" ? "Real engine" : "API synthetic demo engine"}
              action={
                <button onClick={() => downloadCsv("labels.csv", outputCsv(preds))} title="Every checked row, in the six output.csv columns"
                  className="inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs font-medium transition hover:bg-accent">
                  <Download className="h-3.5 w-3.5" /> Download CSV
                </button>
              }>
              <div className="divide-y divide-border">
                {preds.map((p, i) => (
                  <motion.div key={p.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05, duration: 0.4, ease }}>
                    <button onClick={() => setOpen(open === p.id ? null : p.id)} className="flex w-full items-center gap-4 py-3 text-left transition-colors hover:bg-accent/30">
                      <span className="w-24 shrink-0 truncate font-mono text-xs text-muted-foreground">{p.id}</span>
                      <span className="min-w-0 flex-1 truncate text-sm">{byId[p.id]?.text}</span>
                      <VerdictPill label={p.label} />
                      <ConfBar value={p.confidence} />
                      <ChevronDown className={"h-4 w-4 text-muted-foreground transition-transform " + (open === p.id ? "rotate-180" : "")} />
                    </button>
                    <AnimatePresence initial={false}>
                      {open === p.id && (
                        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3, ease }} className="overflow-hidden">
                          <div className="grid gap-4 pb-4 md:grid-cols-2">
                            <div>
                              <div className="eyebrow mb-1">Reason</div>
                              <p className="text-sm">{p.reason}</p>
                              {p.error && <p className="mt-1 font-mono text-xs text-destructive">{p.error}</p>}
                              {p.extraction?.facts?.length ? (
                                <>
                                  <div className="eyebrow mb-1 mt-3">Extracted facts</div>
                                  <div className="space-y-1">
                                    {p.extraction.facts.map((f, j) => (
                                      <div key={j} className="rounded-md bg-surface px-2 py-1 font-mono text-xs">
                                        {f.subject} · <span className="text-primary">{f.attribute}</span> = {String(f.value.value)} {f.value.unit ?? f.value.currency ?? ""}
                                      </div>
                                    ))}
                                  </div>
                                </>
                              ) : null}
                            </div>
                            <div>
                              <div className="eyebrow mb-1">Evidence ({p.evidence_ids.length})</div>
                              <div className="space-y-2">
                                {(p.evidence ?? p.evidence_ids.map((id) => ({ id, text: "", date: "", label: "" as const }))).map((e) => (
                                  <div key={e.id} className="rounded-md border border-border bg-surface p-2 text-xs">
                                    <div className="mb-0.5 flex justify-between font-mono text-muted-foreground"><span>{e.id}</span><span>{e.date}</span></div>
                                    {e.text}
                                  </div>
                                ))}
                                {!p.evidence_ids.length && <p className="text-xs text-muted-foreground">No evidence cited.</p>}
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                ))}
              </div>
            </Panel>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
