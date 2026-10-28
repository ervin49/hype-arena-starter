"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, Circle, FastForward, Loader2, Play, RotateCcw, UploadCloud } from "lucide-react";
import { useRun, type RunRecord } from "@/components/run/RunProvider";
import { ArchitectureLegend } from "@/components/dashboard/ArchitectureDiagram";
import { ARIA_LABEL, EDGES, NODES, NODE_H, STROKE, edgeKey, edgePath, nodeW, type Flow, type NodeId } from "@/lib/architecture";
import { SKIPPED_EDGES, SKIPPED_NODES, nodeBadges, runSteps, type RunStep } from "@/lib/run-steps";
import { cn } from "@/lib/utils";

const STEP_MS = 1300;
const FIRST_STEP_MS = 450;
// How long a line takes to draw; its target node appears when the line arrives.
const EDGE_MS = 800;
// While the engine is working, dots loop along the row-checking path.
const RUNNING_EDGES: [NodeId, NodeId][] = [
  ["F", "X"],
  ["U", "X"],
  ["X", "V"],
  ["V", "C"],
];
const RUNNING_NODES: NodeId[] = ["F", "U", "X", "V", "C"];

// preview: no run yet, the whole diagram dimmed. hidden: not reached yet.
type NodeState = "preview" | "hidden" | "current" | "done" | "skipped" | "running";

export function RunReplay() {
  const { last, running, restored, error, run } = useRun();
  const steps = useMemo(() => (last ? runSteps(last) : []), [last]);
  const badges = useMemo(() => (last ? nodeBadges(last) : {}), [last]);
  const [played, setPlayed] = useState(0);
  const [playing, setPlaying] = useState(false);
  // Whether the lines of the current step have finished drawing.
  const [arrived, setArrived] = useState(false);
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

  // Each new step starts with its lines drawing; its nodes wait for them.
  useEffect(() => {
    if (!playing) {
      setArrived(true);
      return;
    }
    setArrived(false);
    const t = setTimeout(() => setArrived(true), EDGE_MS);
    return () => clearTimeout(t);
  }, [played, playing]);

  const isRunning = running !== null;
  const preview = restored && !last && !isRunning;
  const finished = !isRunning && last !== null && played >= steps.length;
  const current: RunStep | undefined = isRunning ? undefined : steps[played - 1];
  const before = isRunning ? [] : steps.slice(0, Math.max(0, played - 1));
  const reachedNodes = new Set(before.flatMap((s) => s.nodes));
  const litEdges = new Set(
    (isRunning ? [] : steps.slice(0, played)).flatMap((s) => s.edges.map(([a, b]) => edgeKey(a, b))),
  );
  const currentEdges = new Set(current?.edges.map(([a, b]) => edgeKey(a, b)) ?? []);
  const currentReady = !current || current.edges.length === 0 || arrived;
  const skippedEdges = new Set(SKIPPED_EDGES.map(([a, b]) => edgeKey(a, b)));
  const runningEdges = new Set(RUNNING_EDGES.map(([a, b]) => edgeKey(a, b)));

  const nodeState = (id: NodeId): NodeState => {
    if (preview) return "preview";
    if (isRunning) return RUNNING_NODES.includes(id) ? "running" : "hidden";
    if (SKIPPED_NODES.includes(id)) return finished ? "skipped" : "hidden";
    if (current?.nodes.includes(id)) return currentReady ? "current" : reachedNodes.has(id) ? "done" : "hidden";
    if (reachedNodes.has(id)) return "done";
    return "hidden";
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
                if (preview) {
                  return (
                    <path key={key} d={d} fill="none" stroke="var(--border)" strokeWidth={1.8} strokeDasharray={f === "ui" ? "6 5" : undefined} />
                  );
                }
                if (skippedEdges.has(key)) {
                  return (
                    <path
                      key={key}
                      d={d}
                      fill="none"
                      stroke="var(--muted-foreground)"
                      strokeWidth={1.6}
                      strokeDasharray="3 5"
                      opacity={finished ? 0.4 : 0}
                      style={{ transition: "opacity .6s" }}
                    />
                  );
                }
                const live = isRunning && runningEdges.has(key);
                const lit = litEdges.has(key) || live;
                // The arrowhead appears once the line has reached its node.
                const headed = live || (lit && (!currentEdges.has(key) || arrived));
                return (
                  <g key={key}>
                    <path
                      d={d}
                      fill="none"
                      stroke={STROKE[f]}
                      strokeWidth={2.4}
                      pathLength={1}
                      strokeDasharray="1 1"
                      strokeDashoffset={lit ? 0 : 1}
                      markerEnd={headed ? `url(#run-arrow-${f})` : undefined}
                      style={{ transition: `stroke-dashoffset ${EDGE_MS}ms ease-out` }}
                    />
                    {currentEdges.has(key) && !arrived && (
                      <circle key={`dot-${played}`} r={5} fill={STROKE[f]}>
                        <animateMotion dur={`${EDGE_MS}ms`} fill="freeze" path={d} />
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
                const visible = state !== "hidden";
                return (
                  <g
                    key={node.id}
                    opacity={!visible ? 0 : state === "preview" ? 0.5 : state === "skipped" ? 0.4 : 1}
                    style={{
                      transformBox: "fill-box",
                      transformOrigin: "center",
                      transform: visible ? "scale(1)" : "scale(0.85)",
                      transition: "opacity .45s ease-out, transform .45s cubic-bezier(.2,.9,.3,1.3)",
                    }}
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
                      stroke={state === "preview" ? "var(--border)" : state === "skipped" ? "var(--muted-foreground)" : color}
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

        <Timeline steps={steps} played={isRunning ? 0 : played} finished={finished} running={running} hasRun={last !== null} />
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

// Lists only the steps reached so far; each one rises in as the replay gets to it.
function Timeline({ steps, played, finished, running, hasRun }: {
  steps: RunStep[];
  played: number;
  finished: boolean;
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
          {steps.slice(0, played).map((s, i) => {
            const isCurrent = i === played - 1 && !finished;
            return (
              <li key={s.id} className="flex animate-rise-in gap-3">
                <span className="mt-0.5 shrink-0">
                  {isCurrent ? (
                    <span className="grid size-5 place-items-center">
                      <span className="size-3 animate-ping rounded-full bg-primary" />
                    </span>
                  ) : (
                    <CheckCircle2 className="size-5 text-primary" />
                  )}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-heading">
                    {i + 1}. {s.title}
                  </p>
                  <p className="mt-0.5 text-sm text-muted-foreground">{s.detail}</p>
                </div>
              </li>
            );
          })}
          {finished && (
            <li className="flex animate-rise-in gap-3 opacity-60">
              <Circle className="mt-0.5 size-5 shrink-0 text-muted-foreground" strokeDasharray="3 3" />
              <p className="text-sm text-muted-foreground">
                Not in a live run: the template generator, validation and output.csv, which the batch runner does for the 1,000 claims.
              </p>
            </li>
          )}
        </ol>
      )}
    </div>
  );
}
