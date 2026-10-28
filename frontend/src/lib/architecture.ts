// Layout of the architecture diagram, shared by the static card on the
// dashboard and the animated run replay on /architecture.

export type Flow = "cls" | "gen" | "ui" | "both";

export interface ArchNode {
  id: NodeId;
  x: number;
  y: number;
  w?: number;
  title: string;
  // The technique this stage uses, shown on every box.
  tech: string;
  sub: string;
  flow: Flow;
}

export type NodeId = "P" | "L" | "U" | "K" | "X" | "F" | "G" | "V" | "Q" | "C" | "O";
export type Edge = [NodeId, NodeId, Flow];

export const NODE_W = 170;
export const NODE_H = 74;
// Height of the diagram's viewBox, fitting the lowest box.
export const VIEW_H = 414;

export const NODES: ArchNode[] = [
  { id: "P", x: 20, y: 30, title: "Practice rows", tech: "training + evidence data", sub: "labels + JSON forms", flow: "both" },
  { id: "L", x: 20, y: 150, title: "Lexicon", tech: "longest-first alias match", sub: "subjects, aliases, events", flow: "both" },
  { id: "U", x: 20, y: 270, title: "New row", tech: "CSV parser", sub: "text + date", flow: "cls" },
  { id: "K", x: 240, y: 30, title: "Evidence base", tech: "temporal knowledge base", sub: "facts with history", flow: "both" },
  { id: "X", x: 240, y: 190, title: "Extraction", tech: "parser + naive Bayes", sub: "text → facts", flow: "cls" },
  { id: "F", x: 240, y: 320, title: "Frontend", tech: "Next.js + API proxy", sub: "diagram + CSV upload", flow: "ui" },
  { id: "G", x: 460, y: 30, title: "Template generator", tech: "timeline templates", sub: "5 claim types", flow: "gen" },
  { id: "V", x: 460, y: 190, title: "Temporal check", tech: "interval rules over dates", sub: "logic at the row's date", flow: "cls" },
  { id: "Q", x: 680, y: 30, title: "Validation", tech: "rule validator + schema", sub: "schema, text, evidence", flow: "gen" },
  { id: "C", x: 680, y: 190, title: "Verdict", tech: "logistic regression", sub: "label, confidence, why", flow: "cls" },
  { id: "O", x: 880, y: 110, w: 150, title: "output.csv", tech: "atomic CSV write", sub: "labels + 1,000 claims", flow: "both" },
];

export const EDGES: Edge[] = [
  ["P", "K", "both"],
  ["K", "G", "gen"],
  ["G", "Q", "gen"],
  ["Q", "O", "gen"],
  ["L", "X", "cls"],
  ["U", "X", "cls"],
  ["X", "V", "cls"],
  ["K", "V", "cls"],
  ["V", "C", "cls"],
  ["C", "O", "cls"],
  ["F", "X", "ui"],
  ["C", "F", "ui"],
];

export const STROKE: Record<Flow, string> = {
  cls: "var(--primary)",
  gen: "var(--indigo)",
  ui: "var(--primary)",
  both: "var(--muted-foreground)",
};

export const nodeById = Object.fromEntries(NODES.map((n) => [n.id, n])) as Record<NodeId, ArchNode>;
export const nodeW = (n: ArchNode) => n.w ?? NODE_W;
export const edgeKey = (a: NodeId, b: NodeId) => `${a}${b}`;

export function edgePath(from: NodeId, to: NodeId): string {
  const a = nodeById[from];
  const b = nodeById[to];
  const H = NODE_H;
  // Vertical hops (frontend ↔ extraction, evidence → check) leave from the
  // top/bottom; everything else flows left to right.
  if (a.id === "F" && b.id === "X") {
    const x = a.x + nodeW(a) / 2;
    return `M ${x} ${a.y} L ${x} ${b.y + H}`;
  }
  if (a.id === "C" && b.id === "F") {
    const x1 = a.x + nodeW(a) / 2, y1 = a.y + H, x2 = b.x + nodeW(b), y2 = b.y + H / 2;
    return `M ${x1} ${y1} C ${x1} ${y2}, ${x1} ${y2}, ${x2} ${y2}`;
  }
  if (a.id === "K" && b.id === "V") {
    const x1 = a.x + nodeW(a), y1 = a.y + H - 12, x2 = b.x + nodeW(b) / 2, y2 = b.y;
    return `M ${x1} ${y1} C ${x2} ${y1}, ${x2} ${y1}, ${x2} ${y2}`;
  }
  const x1 = a.x + nodeW(a), y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2;
  const dx = Math.max(24, (x2 - x1) / 2);
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
}

export const ARIA_LABEL =
  "Architecture: practice rows and lexicon build an evidence base; new rows are extracted into facts, checked at their date and labelled; a template generator writes claims that are validated; both go to output.csv; the frontend sends rows to extraction and shows verdicts.";
