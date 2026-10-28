import type { RunRecord } from "@/components/run/RunProvider";
import type { NodeId } from "./architecture";

// The steps of one live run, in the order data moves through the system, each
// described with numbers from that run's response. A live run only labels
// rows; the claim generator, validation and output.csv belong to the batch
// runner and are marked as skipped.

export interface RunStep {
  id: string;
  title: string;
  detail: string;
  nodes: NodeId[];
  edges: [NodeId, NodeId][];
}

export const SKIPPED_NODES: NodeId[] = ["G", "Q", "O"];
export const SKIPPED_EDGES: [NodeId, NodeId][] = [
  ["K", "G"],
  ["G", "Q"],
  ["Q", "O"],
  ["C", "O"],
];

const n = (x: number) => x.toLocaleString("en-US");
const plural = (x: number, one: string, many = `${one}s`) => `${n(x)} ${x === 1 ? one : many}`;

export interface RunStats {
  rows: number;
  labelled: number;
  toCheck: number;
  checked: number;
  facts: number;
  complete: number;
  noFacts: number;
  citations: number;
  distinctSources: number;
  withEvidence: number;
  verdicts: { true: number; false: number; unsure: number };
  avgConfidence: number | null;
  failed: number;
  seconds: number;
}

export function runStats(run: RunRecord): RunStats {
  const { rows, predictions } = run.response;
  const labelled = rows.filter((r) => r.label !== "").length;
  const verdicts = { true: 0, false: 0, unsure: 0 };
  let facts = 0, complete = 0, noFacts = 0, citations = 0, withEvidence = 0, failed = 0;
  const sources = new Set<string>();
  const confs: number[] = [];
  for (const p of predictions) {
    verdicts[p.label]++;
    const f = p.extraction?.facts.length ?? 0;
    facts += f;
    if (f === 0) noFacts++;
    if (p.extraction?.complete) complete++;
    citations += p.evidence_ids.length;
    if (p.evidence_ids.length) withEvidence++;
    p.evidence_ids.forEach((id) => sources.add(id));
    if (p.confidence != null) confs.push(p.confidence);
    if (p.error) failed++;
  }
  return {
    rows: rows.length,
    labelled,
    toCheck: rows.length - labelled,
    checked: predictions.length,
    facts,
    complete,
    noFacts,
    citations,
    distinctSources: sources.size,
    withEvidence,
    verdicts,
    avgConfidence: confs.length ? confs.reduce((a, b) => a + b, 0) / confs.length : null,
    failed,
    seconds: (run.finishedAt - run.startedAt) / 1000,
  };
}

export function runSteps(run: RunRecord): RunStep[] {
  const s = runStats(run);
  const demo = run.response.demo_mode;
  const v = s.verdicts;
  return [
    {
      id: "load",
      title: "Practice rows & lexicon",
      detail: demo
        ? "Demo mode: the API runs a synthetic engine, so no real evidence is loaded."
        : "Loaded once when the API started, not on every run.",
      nodes: ["P", "L"],
      edges: [],
    },
    {
      id: "kb",
      title: "Evidence base",
      detail: demo
        ? "Demo mode: no evidence base; verdicts are synthetic."
        : "Built at startup from the practice rows: every fact with the dates it was stated.",
      nodes: ["K"],
      edges: [["P", "K"]],
    },
    {
      id: "upload",
      title: "Upload",
      detail: `${run.file}: ${plural(s.rows, "row")}, ${n(s.toCheck)} to check, ${n(s.labelled)} already labelled.`,
      nodes: ["F", "U"],
      edges: [],
    },
    {
      id: "extract",
      title: "Extraction",
      detail:
        `${plural(s.facts, "fact")} from ${plural(s.checked, "row")}; ${n(s.complete)} complete` +
        (s.noFacts ? `, ${n(s.noFacts)} with no facts found.` : "."),
      nodes: ["X"],
      edges: [
        ["F", "X"],
        ["U", "X"],
        ["L", "X"],
      ],
    },
    {
      id: "check",
      title: "Temporal check",
      detail:
        `${plural(s.citations, "evidence citation")} (${plural(s.distinctSources, "distinct source row")}) ` +
        `for ${n(s.withEvidence)} of ${plural(s.checked, "row")}, each checked at its row's date.`,
      nodes: ["V"],
      edges: [
        ["X", "V"],
        ["K", "V"],
      ],
    },
    {
      id: "verdict",
      title: "Verdict",
      detail:
        `${n(v.true)} true · ${n(v.false)} false · ${n(v.unsure)} unsure` +
        (s.avgConfidence == null ? "." : `; average confidence ${Math.round(s.avgConfidence * 100)}%.`) +
        (s.failed ? ` ${plural(s.failed, "row")} failed in the engine.` : ""),
      nodes: ["C"],
      edges: [["V", "C"]],
    },
    {
      id: "show",
      title: "Shown in the frontend",
      detail: `The engine answered in ${s.seconds.toFixed(2)} s; every verdict is on the dashboard.`,
      nodes: ["F"],
      edges: [["C", "F"]],
    },
  ];
}

// Short figure printed under each node once its step has played.
export function nodeBadges(run: RunRecord): Partial<Record<NodeId, string>> {
  const s = runStats(run);
  const demo = run.response.demo_mode;
  return {
    P: demo ? "not used" : "at startup",
    L: demo ? "not used" : "at startup",
    K: demo ? "not used" : "at startup",
    U: plural(s.toCheck, "row") + " to check",
    X: plural(s.facts, "fact"),
    V: plural(s.citations, "citation"),
    C: `${n(s.verdicts.true)} T · ${n(s.verdicts.false)} F · ${n(s.verdicts.unsure)} U`,
    F: `${s.seconds.toFixed(2)} s`,
  };
}
