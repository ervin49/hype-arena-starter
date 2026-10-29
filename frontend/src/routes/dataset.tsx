import { createFileRoute } from "@tanstack/react-router";
import { AnimatePresence, motion } from "motion/react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useMemo, useState } from "react";
import practice from "@/data/practice.json";
import type { Label } from "@/lib/arena";
import { PageHeader, Panel, Reveal, VerdictPill, ease } from "@/components/arena/ui";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/dataset")({
  head: () => ({
    meta: [
      { title: "Dataset — Hype Arena" },
      {
        name: "description",
        content: "Explore the 1,897 labelled practice sentences of the Hooly universe.",
      },
      { property: "og:title", content: "Dataset — Hype Arena" },
      {
        property: "og:description",
        content: "Explore the labelled practice sentences of the Hooly universe.",
      },
    ],
  }),
  component: Dataset,
});

const PER = 25;
const FILTERS = ["all", "true", "false", "unsure"] as const;

function Dataset() {
  const [q, setQ] = useState("");
  const [f, setF] = useState<(typeof FILTERS)[number]>("all");
  const [page, setPage] = useState(0);
  const rows = useMemo(
    () =>
      practice.rows.filter(
        (r) =>
          (f === "all" || r.label === f) &&
          (r.text.toLowerCase().includes(q.toLowerCase()) || r.id.includes(q)),
      ),
    [q, f],
  );
  const pages = Math.max(1, Math.ceil(rows.length / PER));
  const slice = rows.slice(page * PER, page * PER + PER);

  return (
    <>
      <PageHeader eyebrow="data/practice.csv" title="Practice dataset" />
      <Reveal className="mb-4 flex flex-wrap items-center gap-2">
        {FILTERS.map((x) => (
          <button
            key={x}
            onClick={() => {
              setF(x);
              setPage(0);
            }}
            className="relative rounded-full px-3 py-1.5 text-xs"
          >
            {f === x && (
              <motion.span
                layoutId="ds-tab"
                className="absolute inset-0 rounded-full bg-primary"
                transition={{ type: "spring", stiffness: 400, damping: 32 }}
              />
            )}
            <span
              className={cn(
                "relative font-mono",
                f === x ? "text-primary-foreground" : "text-muted-foreground",
              )}
            >
              {x}{" "}
              <span className="opacity-60">
                {x === "all" ? practice.total : (practice.labels as Record<string, number>)[x]}
              </span>
            </span>
          </button>
        ))}
        <div className="relative ml-auto">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(0);
            }}
            placeholder="Search text or id"
            className="w-64 rounded-lg border border-input bg-surface py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </Reveal>
      <Reveal delay={0.1}>
        <Panel>
          <div className="grid grid-cols-[80px_100px_1fr_90px] gap-4 border-b border-border pb-2 eyebrow">
            <span>id</span>
            <span>date</span>
            <span>text</span>
            <span>label</span>
          </div>
          <AnimatePresence mode="wait">
            <motion.div
              key={`${f}-${q}-${page}`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2, ease }}
            >
              {slice.map((r, i) => (
                <motion.div
                  key={r.id}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.012, duration: 0.25 }}
                  className="grid grid-cols-[80px_100px_1fr_90px] items-center gap-4 border-b border-border/60 py-2.5 text-sm transition-colors hover:bg-accent/30"
                >
                  <span className="font-mono text-xs text-muted-foreground">{r.id}</span>
                  <span className="font-mono text-xs text-muted-foreground">{r.date}</span>
                  <span>{r.text}</span>
                  <VerdictPill label={r.label as Label} />
                </motion.div>
              ))}
              {!slice.length && (
                <p className="py-12 text-center text-sm text-muted-foreground">No rows match.</p>
              )}
            </motion.div>
          </AnimatePresence>
          <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
            <span>{rows.length.toLocaleString()} rows</span>
            <div className="flex items-center gap-2">
              <button
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
                className="rounded-md border border-border p-1.5 transition hover:bg-accent disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="font-mono">
                {page + 1} / {pages}
              </span>
              <button
                disabled={page >= pages - 1}
                onClick={() => setPage(page + 1)}
                className="rounded-md border border-border p-1.5 transition hover:bg-accent disabled:opacity-40"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        </Panel>
      </Reveal>
    </>
  );
}
