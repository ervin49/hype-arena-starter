"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, Circle, FastForward, Loader2, Play, RotateCcw, UploadCloud } from "lucide-react";
import { useRun, type RunRecord } from "@/components/run/RunProvider";
import { ArchitectureLegend } from "@/components/dashboard/ArchitectureDiagram";
import { ARIA_LABEL, EDGES, NODES, NODE_H, STROKE, edgeKey, edgePath, nodeW, type Flow, type NodeId } from "@/lib/architecture";
import { SKIPPED_EDGES, SKIPPED_NODES, nodeBadges, runSteps, type RunStep } from "@/lib/run-steps";
import { cn } from "@/lib/utils";

const STEP_MS = 1200;
const FIRST_STEP_MS = 450;
// While the engine is working, dots loop along the row-checking path.
const RUNNING_EDGES: [NodeId, NodeId][] = [
  ["F", "X"],
  ["U", "X"],
  ["X", "V"],
  ["V", "C"],
];
const RUNNING_NODES: NodeId[] = ["F", "U", "X", "V", "C"];

type NodeState = "pending" | "current" | "done" | "skipped" | "running";

export function RunReplay() {
  const { last, running, error, run } = useRun();
  const steps = useMemo(() => (last ? runSteps(last) : []), [last]);
  const badges = useMemo(() => (last ? nodeBadges(last) : {}), [last]);
  const [played, setPlayed] = useState(0);
  const [playing, setPlaying] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  // A new run, or opening this tab, starts the replay from the left.
  useEffect(() => {
    if (!last) return;
    const reduce = typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setPlayed(steps.length);
      setPlaying(false);
    } else {
      setPlayed(0);
      setPlaying(true);
    }
  }, [last, steps.length]);

  useEffect(() => {
    if (!playing) return;
    if (played >= steps.length) {
      setPlaying(false);
      return;
    }
    const t = setTimeout(() => setPlayed((p) => p + 1), played === 0 ? FIRST_STEP_MS : STEP_MS);
    return () => clearTimeout(t);
  }, [playing, played, steps.length]);

  const isRunning = running !== null;
  const shown = isRunning ? [] : steps.slice(0, played);
  const current: RunStep | undefined = isRunning ? undefined : steps[played - 1];
  const litNodes = new Set(shown.flatMap((s) => s.nodes));
  const litEdges = new Set(shown.flatMap((s) => s.edges.map(([a, b]) => edgeKey(a, b))));
  const currentNodes = new Set(current?.nodes ?? []);
  const currentEdges = new Set(current?.edges.map(([a, b]) => edgeKey(a, b)) ?? []);
  const skippedEdges = new Set(SKIPPED_EDGES.map(([a, b]) => edgeKey(a, b)));
  const runningEdges = new Set(RUNNING_EDGES.map(([a, b]) => edgeKey(a, b)));
  const showSkipped = !isRunning && last !== null;

  const nodeState = (id: NodeId): NodeState => {
    if (isRunning) return RUNNING_NODES.includes(id) ? "running" : "pending";
    if (showSkipped && SKIPPED_NODES.includes(id)) return "skipped";
    if (currentNodes.has(id)) return "current";
    if (litNodes.has(id)) return "done";
    return "pending";
  };

  const replay = () => {
    setPlayed(0);
    setPlaying(true);
  };
  const skip = () => {
    setPlayed(steps.length);
    setPlaying(false);
  };

  return (
    <div className="space-y-6">
      <RunHeader
        last={last}
        running={running}
        playing={playing}
        done={played >= steps.length}
        onReplay={replay}
        onSkip={skip}
        onPick={() => fileInput.current?.click()}
      />
      <input
        ref={fileInput}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) run(f);
          e.target.value = "";
        }}
      />

      {error && !isRunning && (
        <div role="alert" className="card-soft flex gap-3 bg-bad-soft p-5 text-bad">
          <AlertTriangle className="mt-0.5 size-5 shrink-0" />
          <div>
            <p className="font-semibold">The last run failed: {error.message}</p>
            {error.detail && <p className="mt-1 break-words font-mono text-xs">{error.detail}</p>}
            <p className="mt-2 text-xs opacity-80">Nothing is replayed for a failed run.</p>
          </div>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="card-soft p-5 sm:p-6">
          <div className="overflow-x-auto">
            <svg viewBox="0 0 1040 400" className="h-auto w-full min-w-[720px]" role="img" aria-label={ARIA_LABEL}>
              <defs>
                {(Object.keys(STROKE) as Flow[]).map((f) => (
                  <marker key={f} id={`run-arrow-${f}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                    <path d="M0,0 L10,5 L0,10 z" fill={STROKE[f]} />
                  </marker>
                ))}
              </defs>

              {EDGES.map(([a, b, f]) => {
                const key = edgeKey(a, b);
                const d = edgePath(a, b);
                const lit = litEdges.has(key);
                const skipped = showSkipped && skippedEdges.has(key);
                const live = isRunning && runningEdges.has(key);
                return (
                  <g key={key}>
                    <path
                      d={d}
                      fill="none"
                      stroke={skipped ? "var(--muted-foreground)" : "var(--border)"}
                      strokeWidth={1.8}
                      strokeDasharray={skipped ? "3 5" : f === "ui" ? "6 5" : undefined}
                      opacity={skipped ? 0.45 : 1}
                    />
                    <path
                      d={d}
                      fill="none"
                      stroke={STROKE[f]}
                      strokeWidth={2.4}
                      pathLength={1}
                      strokeDasharray="1 1"
                      strokeDashoffset={lit || live ? 0 : 1}
                      markerEnd={lit || live ? `url(#run-arrow-${f})` : undefined}
                      style={{ transition: "stroke-dashoffset .8s ease-out" }}
                    />
                    {currentEdges.has(key) && (
                      <circle key={`dot-${played}`} r={5} fill={STROKE[f]}>
                        <animateMotion dur="0.8s" fill="freeze" path={d} />
                        <animate attributeName="opacity" values="1;1;0" keyTimes="0;0.8;1" dur="0.8s" fill="freeze" />
                      </circle>
                    )}
                    {live && (
                      <circle r={4.5} fill={STROKE[f]}>
                        <animateMotion dur="1.1s" repeatCount="indefinite" path={d} />
                      </circle>
                    )}
                  </g>
                );
              })}

              {NODES.map((node) => {
                const state = nodeState(node.id);
                const color = STROKE[node.flow];
                // The frontend first sends the file; its answer time shows only once the last step has played.
                const badge = node.id === "F" && played < steps.length ? "sent the CSV" : badges[node.id];
                const sub =
                  state === "skipped"
                    ? "not in a live run"
                    : (state === "done" || state === "current") && badge
                      ? badge
                      : node.sub;
                return (
                  <g
                    key={node.id}
                    style={{ transition: "opacity .4s" }}
                    opacity={state === "pending" ? 0.5 : state === "skipped" ? 0.45 : 1}
                  >
                    {(state === "current" || state === "running") && (
                      <rect
                        x={node.x - 5}
                        y={node.y - 5}
                        width={nodeW(node) + 10}
                        height={NODE_H + 10}
                        rx={18}
                        fill="none"
                        stroke={color}
                        strokeWidth={3}
                      >
                        <animate attributeName="opacity" values="0.6;0.05;0.6" dur="1.3s" repeatCount="indefinite" />
                      </rect>
                    )}
                    <rect
                      x={node.x}
                      y={node.y}
                      width={nodeW(node)}
                      height={NODE_H}
                      rx={14}
                      fill={state === "done" || state === "current" ? "var(--accent)" : "var(--card)"}
                      stroke={state === "pending" ? "var(--border)" : state === "skipped" ? "var(--muted-foreground)" : color}
                      strokeWidth={state === "current" ? 2.4 : 1.5}
                      strokeDasharray={state === "skipped" ? "4 4" : node.flow === "ui" ? "5 4" : undefined}
                      style={{ filter: "drop-shadow(0 6px 12px var(--node-shadow))", transition: "fill .4s, stroke .4s" }}
                    />
                    <text x={node.x + 14} y={node.y + 24} fontSize={14} fontWeight={600} fill="var(--heading)">
                      {node.title}
                    </text>
                    <text
                      x={node.x + 14}
                      y={node.y + 43}
                      fontSize={12}
                      fontWeight={sub === badge ? 600 : 400}
                      fill={sub === badge ? "var(--primary)" : "var(--muted-foreground)"}
                    >
                      {sub}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
          <ArchitectureLegend />
        </div>

        <Timeline steps={steps} played={isRunning ? 0 : played} running={running} hasRun={last !== null} />
      </div>
    </div>
  );
}

function RunHeader({ last, running, playing, done, onReplay, onSkip, onPick }: {
  last: RunRecord | null;
  running: { file: string; startedAt: number } | null;
  playing: boolean;
  done: boolean;
  onReplay: () => void;
  onSkip: () => void;
  onPick: () => void;
}) {
  const btn = "inline-flex h-10 items-center gap-2 rounded-full px-4 text-sm font-semibold transition disabled:opacity-50";
  return (
    <div className="card-soft flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
      <div className="min-w-0">
        {running ? (
          <>
            <p className="flex items-center gap-2 text-sm font-semibold text-primary">
              <Loader2 className="size-4 animate-spin" /> Running the engine…
            </p>
            <p className="mt-1 truncate text-sm text-muted-foreground">{running.file}</p>
          </>
        ) : last ? (
          <>
            <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-heading">
              <span className="truncate">{last.file}</span>
              {last.response.demo_mode && (
                <span className="rounded-full bg-warn-soft px-2 py-0.5 text-[11px] font-semibold text-warn">simulated</span>
              )}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Run at {new Date(last.startedAt).toLocaleTimeString()} · answered in {((last.finishedAt - last.startedAt) / 1000).toFixed(2)} s ·{" "}
              {last.response.predictions.length.toLocaleString("en-US")} rows checked
            </p>
          </>
        ) : (
          <>
            <p className="text-sm font-semibold text-heading">No run yet</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Run a CSV here or on the{" "}
              <Link href="/#upload" className="font-semibold text-primary hover:underline">
                dashboard
              </Link>{" "}
              and its steps will play on the diagram.
            </p>
          </>
        )}
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        {last && !running && (
          <>
            <button onClick={onReplay} className={cn(btn, "bg-accent text-primary hover:opacity-90")}>
              {done ? <RotateCcw className="size-4" /> : <Play className="size-4" />}
              {done ? "Replay" : "Restart"}
            </button>
            {playing && (
              <button onClick={onSkip} className={cn(btn, "bg-muted text-muted-foreground hover:text-primary")}>
                <FastForward className="size-4" /> Skip
              </button>
            )}
          </>
        )}
        <button onClick={onPick} disabled={running !== null} className={cn(btn, "bg-primary text-primary-foreground shadow-soft hover:opacity-90")}>
          <UploadCloud className="size-4" /> Run a CSV
        </button>
      </div>
    </div>
  );
}

function Timeline({ steps, played, running, hasRun }: {
  steps: RunStep[];
  played: number;
  running: { file: string } | null;
  hasRun: boolean;
}) {
  return (
    <div className="card-soft p-5 sm:p-6">
      <h2 className="text-lg font-bold">Steps of this run</h2>
      {running ? (
        <p className="mt-3 text-sm text-muted-foreground">The engine is working on {running.file}. The steps play as soon as it answers.</p>
      ) : !hasRun ? (
        <p className="mt-3 text-sm text-muted-foreground">Nothing to show until a CSV has been run.</p>
      ) : (
        <ol className="mt-4 space-y-4">
          {steps.map((s, i) => {
            const state = i < played - 1 ? "done" : i === played - 1 ? "current" : "pending";
            return (
              <li key={s.id} className={cn("flex gap-3 transition-opacity", state === "pending" && "opacity-45")}>
                <span className="mt-0.5 shrink-0">
                  {state === "done" ? (
                    <CheckCircle2 className="size-5 text-primary" />
                  ) : state === "current" ? (
                    <span className="grid size-5 place-items-center">
                      <span className="size-3 animate-ping rounded-full bg-primary" />
                    </span>
                  ) : (
                    <Circle className="size-5 text-muted-foreground" />
                  )}
                </span>
                <div className="min-w-0">
                  <p className={cn("text-sm font-semibold", state === "pending" ? "text-muted-foreground" : "text-heading")}>
                    {i + 1}. {s.title}
                  </p>
                  {state !== "pending" && <p className="mt-0.5 text-sm text-muted-foreground">{s.detail}</p>}
                </div>
              </li>
            );
          })}
          <li className="flex gap-3 opacity-60">
            <Circle className="mt-0.5 size-5 shrink-0 text-muted-foreground" strokeDasharray="3 3" />
            <p className="text-sm text-muted-foreground">
              Not in a live run: the template generator, validation and output.csv, which the batch runner does for the 1,000 claims.
            </p>
          </li>
        </ol>
      )}
    </div>
  );
}
