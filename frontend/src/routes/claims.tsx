import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { Download, Search, Unplug } from "lucide-react";
import { useMemo, useState } from "react";
import { api, type Claim } from "@/lib/arena";
import { downloadCsv, outputCsv } from "@/lib/csv";
import { ConfBar, PageHeader, Panel, Reveal, ease } from "@/components/arena/ui";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/claims")({
  head: () => ({
    meta: [
      { title: "Claims — Hype Arena" },
      { name: "description", content: "Browse the 1,000 generated claims about Hooly with their confidence and evidence." },
      { property: "og:title", content: "Claims — Hype Arena" },
      { property: "og:description", content: "Browse the 1,000 generated claims with their evidence." },
    ],
  }),
  component: Claims,
});

const TYPES = ["all", "compare", "change", "at_event", "fact", "relation"] as const;
const FALLBACK = { compare: 430, change: 317, at_event: 247, fact: 4, relation: 2 };

function Claims() {
  const q = useQuery({ queryKey: ["claims"], queryFn: api.claims, retry: false, enabled: typeof window !== "undefined" });
  const [type, setType] = useState<(typeof TYPES)[number]>("all");
  const [s, setS] = useState("");
  const [sel, setSel] = useState<Claim | null>(null);
  const claims = q.data?.claims ?? [];
  const counts = useMemo(() => {
    if (!claims.length) return FALLBACK as Record<string, number>;
    const c: Record<string, number> = {};
    claims.forEach((x) => (c[x.type] = (c[x.type] ?? 0) + 1));
    return c;
  }, [claims]);
  const list = claims.filter((c) => (type === "all" || c.type === type) && c.text.toLowerCase().includes(s.toLowerCase())).slice(0, 200);

  return (
    <>
      <PageHeader eyebrow="GET /claims" title="Generated claims">
        {claims.length > 0 && (
          <button onClick={() => downloadCsv("claims.csv", outputCsv([], claims))} title="All claims, in the six output.csv columns"
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm font-medium transition hover:bg-accent">
            <Download className="h-4 w-4" /> Download CSV
          </button>
        )}
      </PageHeader>
      <Reveal className="mb-4 flex flex-wrap items-center gap-2">
        {TYPES.map((t) => (
          <button key={t} onClick={() => setType(t)} className="relative rounded-full px-3 py-1.5 text-xs">
            {type === t && <motion.span layoutId="claim-tab" className="absolute inset-0 rounded-full bg-primary" transition={{ type: "spring", stiffness: 400, damping: 32 }} />}
            <span className={cn("relative font-mono", type === t ? "text-primary-foreground" : "text-muted-foreground")}>
              {t} {t !== "all" && <span className="opacity-60">{counts[t] ?? 0}</span>}
            </span>
          </button>
        ))}
        <div className="relative ml-auto">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input value={s} onChange={(e) => setS(e.target.value)} placeholder="Search claims"
            className="w-64 rounded-lg border border-input bg-surface py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
        </div>
      </Reveal>

      {!claims.length ? (
        <Reveal>
          <Panel>
            <div className="flex flex-col items-center py-16 text-center">
              <div className="grid h-12 w-12 place-items-center rounded-full bg-muted"><Unplug className="h-5 w-5 text-muted-foreground" /></div>
              <h3 className="mt-4 font-medium">{q.isLoading ? "Loading claims…" : "Connect the engine to browse claims"}</h3>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                {q.isError && <span className="block text-destructive">{(q.error as Error).message}</span>}
                Claims are built when the API starts. Run <span className="font-mono text-foreground">.venv/bin/uvicorn api.main:app --port 8000</span> and they'll appear here with their evidence. Counts above come from the last batch run.
              </p>
            </div>
          </Panel>
        </Reveal>
      ) : (
        <div className="grid gap-4 lg:grid-cols-5">
          <div className="space-y-2 lg:col-span-3">
            {list.map((c, i) => (
              <motion.button key={c.id} onClick={() => setSel(c)}
                initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 15) * 0.03, duration: 0.35, ease }}
                className={cn("panel flex w-full items-center gap-4 p-4 text-left transition-colors hover:border-primary/40", sel?.id === c.id && "border-primary/60")}>
                <span className="w-20 shrink-0 font-mono text-[10px] uppercase text-gen">{c.type}</span>
                <span className="flex-1 text-sm">{c.text}</span>
                <ConfBar value={c.confidence} />
              </motion.button>
            ))}
          </div>
          <div className="lg:col-span-2">
            <div className="sticky top-20">
              <AnimatePresence mode="wait">
                {sel ? (
                  <motion.div key={sel.id} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.3, ease }} className="panel p-5">
                    <div className="eyebrow">{sel.id} · {sel.type}</div>
                    <p className="mt-2 text-lg leading-snug">{sel.text}</p>
                    <div className="eyebrow mb-2 mt-5">Evidence</div>
                    <div className="space-y-2">
                      {sel.evidence.map((e) => (
                        <div key={e.id} className="rounded-md border border-border bg-surface p-2 text-xs">
                          <div className="mb-0.5 flex justify-between font-mono text-muted-foreground"><span>{e.id}</span><span>{e.date}</span></div>{e.text}
                        </div>
                      ))}
                    </div>
                    <div className="eyebrow mb-2 mt-5">Form</div>
                    <pre className="overflow-auto rounded-md bg-background p-3 font-mono text-[11px] text-muted-foreground">{JSON.stringify(sel.form, null, 2)}</pre>
                  </motion.div>
                ) : (
                  <div className="panel p-5 text-sm text-muted-foreground">Select a claim to see its evidence.</div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
