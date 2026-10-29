import { createFileRoute } from "@tanstack/react-router";
import { AnimatePresence, motion } from "motion/react";
import { Check, ChevronLeft, ChevronRight, Pause, Play, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArchDiagram, NODES, NODE_INFO, type NodeId } from "@/components/arena/ArchDiagram";
import { PageHeader, Panel, Reveal } from "@/components/arena/ui";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/architecture")({
  head: () => ({
    meta: [
      { title: "Architecture — Hype Arena" },
      { name: "description", content: "Step-by-step walkthrough of how Hype Arena labels rows and generates 1,000 true claims." },
      { property: "og:title", content: "Architecture — Hype Arena" },
      { property: "og:description", content: "Step-by-step walkthrough of the Hype Arena pipeline." },
    ],
  }),
  component: Arch,
});

const STEP_MS = 5200;
const SMOOTH = [0.45, 0, 0.2, 1] as const;

const REPLAY: { title: string; detail: string; nodes: NodeId[] }[] = [
  { title: "Load the universe", detail: "Practice rows and the lexicon build a temporal evidence base.", nodes: ["P", "L", "K"] },
  { title: "Generate claims", detail: "Templates walk each timeline: compare, change, at_event, fact, relation.", nodes: ["K", "G"] },
  { title: "Validate claims", detail: "Schema, claim-form text and evidence checks — about 2,000 candidates, 1,000 kept.", nodes: ["G", "Q"] },
  { title: "Take a new row", detail: "A sentence with a date arrives from the CSV or this dashboard.", nodes: ["U", "F"] },
  { title: "Extract facts", detail: "Aliases resolve to subjects; text becomes typed facts.", nodes: ["U", "L", "X", "F"] },
  { title: "Check in time", detail: "Each fact is compared with what was true on the row's date.", nodes: ["X", "K", "V"] },
  { title: "Decide", detail: "Calibrated boosted trees give a label, a confidence and a reason.", nodes: ["V", "C"] },
  { title: "Write output", detail: "Labels plus 1,000 claims, written atomically to output.csv.", nodes: ["C", "Q", "O", "F"] },
];

function Arch() {
  const [i, setI] = useState(-1);
  const [playing, setPlaying] = useState(false);
  const [done, setDone] = useState(false);
  const [sel, setSel] = useState<NodeId | null>(null);
  const last = REPLAY.length - 1;

  useEffect(() => {
    if (!playing) return;
    if (i >= last) {
      const t = setTimeout(() => { setPlaying(false); setDone(true); }, STEP_MS);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setI((x) => x + 1), i < 0 ? 400 : STEP_MS);
    return () => clearTimeout(t);
  }, [playing, i, last]);

  // Manual navigation always leaves the finished state.
  const stop = useCallback(() => { setPlaying(false); setDone(false); }, []);
  const start = useCallback(() => {
    if (i >= last) { setI(-1); setDone(false); }
    setPlaying((p) => !p);
  }, [i, last]);

  // Keyboard control for recording: space play/pause, arrows step.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === "INPUT") return;
      if (e.key === " ") { e.preventDefault(); start(); }
      if (e.key === "ArrowRight") { stop(); setI((x) => Math.min(last, x + 1)); }
      if (e.key === "ArrowLeft") { stop(); setI((x) => Math.max(-1, x - 1)); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [last, start, stop]);

  const revealed = useMemo(() => new Set(REPLAY.slice(0, i + 1).flatMap((s) => s.nodes)), [i]);
  const step = i >= 0 ? REPLAY[i] : null;
  const node = NODES.find((n) => n.id === sel && revealed.has(n.id));

  return (
    <>
      <PageHeader eyebrow="How it works" title="Architecture">
        <div className="flex gap-2">
          <button onClick={() => { stop(); setI((x) => Math.max(-1, x - 1)); }} className="rounded-lg border border-border bg-card px-3 text-muted-foreground transition hover:bg-accent hover:text-foreground" aria-label="Previous step">
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button onClick={start} className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-medium text-primary-foreground glow transition hover:brightness-110">
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />} {playing ? "Pause" : i >= last ? "Replay" : i >= 0 ? "Resume" : "Play walkthrough"}
          </button>
          <button onClick={() => { stop(); setI((x) => Math.min(last, x + 1)); }} className="rounded-lg border border-border bg-card px-3 text-muted-foreground transition hover:bg-accent hover:text-foreground" aria-label="Next step">
            <ChevronRight className="h-4 w-4" />
          </button>
          <button onClick={() => { stop(); setI(-1); setSel(null); }} className="rounded-lg border border-border bg-card px-3 text-muted-foreground transition hover:bg-accent hover:text-foreground" aria-label="Reset">
            <RotateCcw className="h-4 w-4" />
          </button>
        </div>
      </PageHeader>

      <Reveal>
        <div className="panel relative overflow-hidden p-6 md:p-10">
          <div className="pointer-events-none absolute inset-0 bg-grid opacity-70" />
          {/* Step caption */}
          <div className="relative mb-8 flex min-h-24 items-start gap-6">
            <AnimatePresence mode="wait">
              {done ? (
                <motion.div key="done" className="flex items-start gap-6"
                  initial={{ opacity: 0, y: 16, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                  exit={{ opacity: 0, y: -12, filter: "blur(6px)" }} transition={{ duration: 1.1, ease: SMOOTH }}>
                  <div className="grid h-14 w-14 shrink-0 place-items-center rounded-full border border-primary/30 bg-primary/10 md:h-16 md:w-16">
                    <Check className="h-7 w-7 text-primary md:h-8 md:w-8" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">The whole system, lit</h2>
                    <p className="mt-2 max-w-2xl text-base text-muted-foreground md:text-lg">Every stage is live: the universe becomes evidence, evidence becomes 1,000 true claims, a new row becomes a verdict.</p>
                  </div>
                </motion.div>
              ) : step ? (
                <motion.div key={i} className="flex items-start gap-6"
                  initial={{ opacity: 0, y: 16, filter: "blur(6px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                  exit={{ opacity: 0, y: -12, filter: "blur(6px)" }} transition={{ duration: 0.9, ease: SMOOTH }}>
                  <div className="font-mono text-5xl font-medium leading-none text-primary tabular-nums md:text-6xl">{String(i + 1).padStart(2, "0")}</div>
                  <div>
                    <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">{step.title}</h2>
                    <p className="mt-2 max-w-2xl text-base text-muted-foreground md:text-lg">{step.detail}</p>
                  </div>
                </motion.div>
              ) : (
                <motion.div key="intro" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.8, ease: SMOOTH }}>
                  <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">From a sentence to a verdict</h2>
                  <p className="mt-2 text-base text-muted-foreground md:text-lg">Press play — or space — to build the system one stage at a time.</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div className="relative">
            <ArchDiagram revealed={revealed} active={step ? new Set(step.nodes) : undefined} selected={sel} onSelect={setSel} finale={done} />
            <AnimatePresence>
              {i < 0 && (
                <motion.button onClick={start} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.9 }}
                  transition={{ duration: 0.6, ease: SMOOTH }}
                  className="absolute left-1/2 top-1/2 grid h-20 w-20 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-primary text-primary-foreground glow">
                  <Play className="ml-1 h-8 w-8" />
                </motion.button>
              )}
            </AnimatePresence>
          </div>

          {/* Progress */}
          <div className="relative mt-8 flex gap-2">
            {REPLAY.map((s, j) => (
              <button key={s.title} onClick={() => { stop(); setI(j); }} className="group flex-1 text-left" aria-label={s.title}>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <motion.div className="h-full rounded-full bg-primary" initial={false}
                    animate={{ width: j < i ? "100%" : j === i ? (playing ? "100%" : "100%") : "0%" }}
                    transition={{ duration: j === i && playing ? STEP_MS / 1000 : 0.6, ease: j === i && playing ? "linear" : SMOOTH }} />
                </div>
                <div className={cn("mt-2 hidden text-[11px] transition-colors duration-700 md:block", j <= i ? "text-foreground" : "text-transparent")}>{s.title}</div>
              </button>
            ))}
          </div>
        </div>
      </Reveal>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <Reveal delay={0.1} className="md:col-span-2">
          <AnimatePresence mode="wait">
            {node ? (
              <motion.div key={node.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 10 }} transition={{ duration: 0.4, ease: SMOOTH }} className="panel p-6">
                <div className="eyebrow">{node.tech}</div>
                <h3 className="mt-1 text-xl font-semibold">{node.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{NODE_INFO[node.id]}</p>
              </motion.div>
            ) : (
              <div className="panel p-6 text-sm text-muted-foreground">Click any visible stage to read what it does. Keys: space play/pause, ← → step.</div>
            )}
          </AnimatePresence>
        </Reveal>
        <Reveal delay={0.15}>
          <Panel title="Hard rules">
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>• The system itself is not an LLM.</li>
              <li>• Runs offline, 2 CPUs, 6 GiB, ≤ 30 min.</li>
              <li>• The universe is the truth — no web facts.</li>
              <li>• Exactly 1,000 claims, every one true.</li>
            </ul>
          </Panel>
        </Reveal>
      </div>
    </>
  );
}
