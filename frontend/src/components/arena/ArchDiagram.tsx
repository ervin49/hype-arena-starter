import { motion } from "motion/react";
import { cn } from "@/lib/utils";

export type NodeId = "P" | "L" | "U" | "K" | "X" | "F" | "G" | "V" | "Q" | "C" | "O";
type Flow = "cls" | "gen" | "ui" | "both";
interface N { id: NodeId; x: number; y: number; w?: number; title: string; tech: string; flow: Flow }

const W = 170, H = 74;
export const NODES: N[] = [
  { id: "P", x: 20, y: 30, title: "Practice rows", tech: "training + evidence", flow: "both" },
  { id: "L", x: 20, y: 150, title: "Lexicon", tech: "longest-first alias match", flow: "both" },
  { id: "U", x: 20, y: 270, title: "New row", tech: "CSV parser", flow: "cls" },
  { id: "K", x: 240, y: 30, title: "Evidence base", tech: "temporal knowledge base", flow: "both" },
  { id: "X", x: 240, y: 190, title: "Extraction", tech: "parser + naive Bayes", flow: "cls" },
  { id: "F", x: 240, y: 320, title: "Frontend", tech: "dashboard + API", flow: "ui" },
  { id: "G", x: 460, y: 30, title: "Template generator", tech: "timeline templates", flow: "gen" },
  { id: "V", x: 460, y: 190, title: "Temporal check", tech: "interval rules over dates", flow: "cls" },
  { id: "Q", x: 680, y: 30, title: "Validation", tech: "rule validator + schema", flow: "gen" },
  { id: "C", x: 680, y: 190, title: "Verdict", tech: "boosted trees + Platt", flow: "cls" },
  { id: "O", x: 880, y: 110, w: 150, title: "output.csv", tech: "labels + 1,000 claims", flow: "both" },
];
export const EDGES: [NodeId, NodeId, Flow][] = [
  ["P", "K", "both"], ["L", "K", "both"], ["K", "G", "gen"], ["G", "Q", "gen"], ["Q", "O", "gen"],
  ["L", "X", "cls"], ["U", "X", "cls"], ["X", "V", "cls"], ["K", "V", "cls"], ["V", "C", "cls"],
  ["C", "O", "cls"], ["F", "X", "ui"], ["C", "F", "ui"],
];
const byId = Object.fromEntries(NODES.map((n) => [n.id, n])) as Record<NodeId, N>;
const w = (n: N) => n.w ?? W;

function path(a: NodeId, b: NodeId) {
  const A = byId[a], B = byId[b];
  if (a === "F" && b === "X") { const x = A.x + w(A) / 2; return `M ${x} ${A.y} L ${x} ${B.y + H}`; }
  if (a === "C" && b === "F") {
    const x1 = A.x + w(A) / 2, y1 = A.y + H, x2 = B.x + w(B), y2 = B.y + H / 2;
    return `M ${x1} ${y1} C ${x1} ${y2}, ${x1} ${y2}, ${x2} ${y2}`;
  }
  if (a === "K" && b === "V") {
    const x1 = A.x + w(A), y1 = A.y + H * 0.75, x2 = B.x + w(B) / 2, y2 = B.y;
    return `M ${x1} ${y1} C ${x2} ${y1}, ${x2} ${y1}, ${x2} ${y2}`;
  }
  const x1 = A.x + w(A), y1 = A.y + H / 2, x2 = B.x, y2 = B.y + H / 2, mx = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`;
}

const stroke: Record<Flow, string> = { cls: "var(--primary)", gen: "var(--gen)", ui: "var(--primary)", both: "var(--muted-foreground)" };

const SMOOTH = [0.45, 0, 0.2, 1] as const;

export function ArchDiagram({ active, onSelect, selected, revealed, finale = false }: {
  active?: Set<NodeId> | undefined;
  onSelect?: (id: NodeId) => void;
  selected?: NodeId | null;
  /** When set, only these stages are visible at all (pitch reveal mode). */
  revealed?: Set<NodeId> | undefined;
  /** Walkthrough finished: every stage lights up in one sweep. */
  finale?: boolean;
}) {
  const lit = (id: NodeId) => finale || !active || active.has(id);
  const shown = (id: NodeId) => !revealed || revealed.has(id);
  const slow = !!revealed;
  const live = !!active || finale;
  return (
    <svg viewBox="0 0 1050 414" className="h-auto w-full overflow-visible">
      <defs>
        {(["cls", "gen", "both"] as const).map((f) => (
          <marker key={f} id={`arr-${f}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill={stroke[f]} />
          </marker>
        ))}
        <filter id="node-glow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="6" stdDeviation="9" floodColor="var(--primary)" floodOpacity="0.35" />
        </filter>
        <filter id="node-glow-strong" x="-45%" y="-45%" width="190%" height="190%">
          <feDropShadow dx="0" dy="0" stdDeviation="16" floodColor="var(--primary)" floodOpacity="0.55" />
        </filter>
        <radialGradient id="finale-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.22" />
          <stop offset="55%" stopColor="var(--primary)" stopOpacity="0.08" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
        </radialGradient>
      </defs>
      <motion.ellipse
        cx={525} cy={207} rx={545} ry={215} fill="url(#finale-glow)"
        initial={false}
        animate={{ opacity: finale ? [0, 1, 0.7, 1] : 0 }}
        transition={finale
          ? { duration: 7, times: [0, 0.22, 0.58, 1], ease: "easeInOut", repeat: Infinity }
          : { duration: 1.2, ease: SMOOTH }}
      />
      {EDGES.map(([a, b, f], i) => {
        const visible = shown(a) && shown(b);
        const on = lit(a) && lit(b);
        const d = path(a, b);
        return (
          <g key={a + b}>
            <motion.path
              d={d} fill="none" stroke={finale && f === "both" ? "var(--primary)" : stroke[f]} strokeWidth={on && live ? (finale ? 2.4 : 2) : 1.5}
              markerEnd={`url(#arr-${(finale && f === "both") || f === "ui" ? "cls" : f})`}
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: visible ? 1 : 0, opacity: visible ? (on ? (finale ? 0.9 : 0.75) : 0.25) : 0 }}
              transition={slow
                ? { pathLength: { duration: 1.6, delay: 0.7, ease: SMOOTH }, opacity: { duration: 1.4, delay: finale ? i * 0.06 : 0, ease: SMOOTH } }
                : { pathLength: { duration: 0.9, delay: 0.3 + i * 0.05 }, opacity: { duration: 0.4 } }}
            />
            {visible && on && live && (
              <motion.path d={d} fill="none" stroke={finale && f === "both" ? "var(--primary)" : stroke[f]} strokeWidth={finale ? 3 : 2.5} className="flow-dash"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                transition={{ duration: 1, delay: slow ? (finale ? 0.4 + i * 0.07 : 2) : 0 }} />
            )}
          </g>
        );
      })}
      {NODES.map((n, i) => {
        const visible = shown(n.id);
        const on = lit(n.id);
        const hot = finale || (!!active && on);
        const sel = selected === n.id;
        const color = finale && n.flow === "both" ? "var(--primary)" : n.flow === "gen" ? "var(--gen)" : n.flow === "both" ? "var(--muted-foreground)" : "var(--primary)";
        const wave = finale ? 0.25 + i * 0.1 : 0;
        return (
          <motion.g
            key={n.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: visible ? (on ? 1 : 0.4) : 0, y: visible ? 0 : 14, scale: hot && slow ? (finale ? 1.05 : 1.04) : 1 }}
            transition={slow ? { duration: 1.4, ease: SMOOTH, delay: finale ? i * 0.1 : 0 } : { duration: 0.5, delay: i * 0.04 }}
            style={{ transformBox: "fill-box", transformOrigin: "center", pointerEvents: visible ? "auto" : "none" }}
            onClick={() => onSelect?.(n.id)}
            className={cn(onSelect && "cursor-pointer")}
          >
            <motion.rect
              x={n.x - 5} y={n.y - 5} width={w(n) + 10} height={H + 10} rx={15}
              fill="none" stroke={color} strokeWidth={1.5} filter="url(#node-glow-strong)"
              initial={false}
              animate={{ opacity: visible && hot ? (finale ? 0.85 : 0.55) : sel ? 0.45 : 0 }}
              transition={{ duration: 1.1, ease: SMOOTH, delay: wave }}
            />
            <rect x={n.x} y={n.y} width={w(n)} height={H} rx={10}
              fill="var(--card)" stroke={sel || hot ? color : "var(--border)"} strokeWidth={sel || hot ? 2 : 1}
              style={{ transition: "stroke 900ms ease, stroke-width 900ms ease", transitionDelay: `${wave * 1000}ms` }}
              filter={hot && slow && !finale ? "url(#node-glow)" : undefined} />
            <rect x={n.x} y={n.y + 14} width={3} height={H - 28} rx={1.5} fill={color} />
            <text x={n.x + 16} y={n.y + 28} fill="var(--foreground)" fontSize={13} fontWeight={600}>{n.title}</text>
            <text x={n.x + 16} y={n.y + 48} fill="var(--muted-foreground)" fontSize={10.5} fontFamily="var(--font-mono)">{n.tech}</text>
          </motion.g>
        );
      })}
    </svg>
  );
}

export const NODE_INFO: Record<NodeId, string> = {
  P: "1,897 labelled sentences of the practice universe, each with its JSON facts. They train the verdict model and are the evidence every new row is judged against.",
  L: "Subjects, aliases, attributes and events. A longest-first alias match maps 'AI Pro' and 'Hooly AI Pro' to the same subject.",
  U: "A new unlabelled sentence: id, text, date. Uploaded as CSV or typed in the live run.",
  K: "Facts with their history: every value a subject's attribute held, and from which date. Lets the system say what was true on any day.",
  X: "Turns text into typed facts (money, date, quantity, name…) with a rule parser backed by naive Bayes for attribute choice.",
  F: "This dashboard. Sends rows to the API and shows verdicts, evidence and the architecture replay.",
  G: "Walks the timelines and fills templates: compare, change, at_event, fact and relation claims.",
  V: "Interval rules: compares each extracted fact with what the evidence base held at the row's date.",
  Q: "Every claim is checked against the schema, the claim-form text rules and its cited evidence. Invalid claims are dropped.",
  C: "Boosted trees over temporal features, self-trained, calibrated with Platt scaling (ECE 0.027). Outputs label, confidence and a reason.",
  O: "One atomic CSV: a label for each unlabelled row plus exactly 1,000 true claims.",
};
