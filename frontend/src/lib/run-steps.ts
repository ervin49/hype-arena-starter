import type { RunRecord } from "@/components/run/RunProvider";
import type { NodeId } from "./architecture";
import type { ClaimsResponse } from "./types";

// The steps of one live run, in the order data moves through the system, each
// described with numbers from that run's response. A live run only labels
// rows. The claims are built once when the API starts, as the batch runner
// builds them; with the API's claim report the generator, validation and
// output.csv play too, otherwise they are marked as skipped.

export interface RunStep {
  id: string;
  title: string;
  detail: string;
  nodes: NodeId[];
  edges: [NodeId, NodeId][];
}

const CLAIM_NODES: NodeId[] = ["G", "Q", "O"];
const CLAIM_EDGES: [NodeId, NodeId][] = [
  ["K", "G"],
  ["G", "Q"],
  ["Q", "O"],
  ["C", "O"],
];

// Claims count only when the API built some; this frontend's own demo mode has none.
export const hasClaims = (claims: ClaimsResponse | null | undefined): claims is ClaimsResponse =>
  !!claims && claims.claims.length > 0;

export function skipped(claims: ClaimsResponse | null | undefined): { nodes: NodeId[]; edges: [NodeId, NodeId][] } {
  return hasClaims(claims) ? { nodes: [], edges: [] } : { nodes: CLAIM_NODES, edges: CLAIM_EDGES };
}

const TYPE_ORDER = ["fact", "compare", "change", "at_event", "relation"];

function typeCounts(report: Record<string, number>, prefix: string): string {
  return TYPE_ORDER.filter((t) => report[`${prefix}.${t}`])
    .map((t) => `${n(report[`${prefix}.${t}`])} ${t.replace("_", " ")}`)
    .join(", ");
}

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

function claimSteps(claims: ClaimsResponse): { build: RunStep[]; write: RunStep } {
  const r = claims.report;
  const rejected = Object.entries(r)
    .filter(([k]) => k.startsWith("rejected."))
    .reduce((a, [, x]) => a + x, 0);
  return {
    build: [
      {
        id: "generate",
        title: "Template generator",
        detail:
          `${plural(r.candidates ?? 0, "candidate claim")} from the evidence base (${typeCounts(r, "candidates")}), ` +
          "built once at startup.",
        nodes: ["G"],
        edges: [["K", "G"]],
      },
      {
        id: "validate",
        title: "Validation",
        detail:
          `${n(r.selected ?? claims.claims.length)} kept, the best supported: each passes the schema, the lexicon, ` +
          `the claim-form rules and its evidence` +
          (rejected ? `; ${plural(rejected, "wording")} rejected.` : "."),
        nodes: ["Q"],
        edges: [["G", "Q"]],
      },
    ],
    write: {
      id: "output",
      title: "output.csv",
      detail:
        `In the batch run: a label for every unlabelled row, and the ${n(claims.claims.length)} claims ` +
        `(${typeCounts(r, "selected")}), written atomically.`,
      nodes: ["O"],
      edges: [
        ["Q", "O"],
        ["C", "O"],
      ],
    },
  };
}

export function runSteps(run: RunRecord, claims?: ClaimsResponse | null): RunStep[] {
  const s = runStats(run);
  const demo = run.response.demo_mode;
  const v = s.verdicts;
  const c = hasClaims(claims) ? claimSteps(claims) : null;
  const steps: RunStep[] = [
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
    ...(c ? c.build : []),
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
  return c ? [...steps, c.write] : steps;
}

// Short figure printed under each node once its step has played.
export function nodeBadges(run: RunRecord, claims?: ClaimsResponse | null): Partial<Record<NodeId, string>> {
  const s = runStats(run);
  const demo = run.response.demo_mode;
  const r = hasClaims(claims) ? claims.report : null;
  return {
    ...(r && {
      G: plural(r.candidates ?? 0, "candidate"),
      Q: `${n(r.selected ?? 0)} valid`,
      O: `${n(r.selected ?? 0)} claims + labels`,
    }),
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
