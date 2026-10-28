type Flow = "gen" | "cls" | "both" | "ui";

interface Node {
  id: string;
  x: number;
  y: number;
  w?: number;
  title: string;
  sub: string;
  flow: Flow;
}

const W = 170;
const H = 58;

const NODES: Node[] = [
  { id: "P", x: 20, y: 30, title: "Practice rows", sub: "labels + JSON forms", flow: "both" },
  { id: "L", x: 20, y: 150, title: "Lexicon", sub: "subjects, aliases, events", flow: "both" },
  { id: "U", x: 20, y: 270, title: "New row", sub: "text + date", flow: "cls" },
  { id: "K", x: 240, y: 30, title: "Evidence base", sub: "facts with history", flow: "both" },
  { id: "X", x: 240, y: 190, title: "Extraction", sub: "text → facts", flow: "cls" },
  { id: "F", x: 240, y: 320, title: "Frontend", sub: "diagram + CSV upload", flow: "ui" },
  { id: "G", x: 460, y: 30, title: "Template generator", sub: "5 claim types", flow: "gen" },
  { id: "V", x: 460, y: 190, title: "Temporal check", sub: "logic at the row's date", flow: "cls" },
  { id: "Q", x: 680, y: 30, title: "Validation", sub: "schema, text, evidence", flow: "gen" },
  { id: "C", x: 680, y: 190, title: "Verdict", sub: "label, confidence, why", flow: "cls" },
  { id: "O", x: 880, y: 110, w: 150, title: "output.csv", sub: "labels + 1,000 claims", flow: "both" },
];

const EDGES: [string, string, Flow][] = [
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

const byId = Object.fromEntries(NODES.map((n) => [n.id, n]));
const w = (n: Node) => n.w ?? W;

function path(a: Node, b: Node): string {
  // Vertical hops (frontend ↔ extraction, evidence → check) leave from the
  // top/bottom; everything else flows left to right.
  if (a.id === "F" && b.id === "X") {
    const x = a.x + w(a) / 2;
    return `M ${x} ${a.y} L ${x} ${b.y + H}`;
  }
  if (a.id === "C" && b.id === "F") {
    const x1 = a.x + w(a) / 2, y1 = a.y + H, x2 = b.x + w(b), y2 = b.y + H / 2;
    return `M ${x1} ${y1} C ${x1} ${y2}, ${x1} ${y2}, ${x2} ${y2}`;
  }
  if (a.id === "K" && b.id === "V") {
    const x1 = a.x + w(a) * 0.7, y1 = a.y + H, x2 = b.x + w(b) * 0.3, y2 = b.y;
    return `M ${x1} ${y1} C ${x1} ${y1 + 50}, ${x2} ${y2 - 50}, ${x2} ${y2}`;
  }
  const x1 = a.x + w(a), y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2;
  const dx = Math.max(24, (x2 - x1) / 2);
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
}

// Literal class names so Tailwind picks them up.
const FLOW_CLASS: Record<Flow, { box: string; edge: string; head: string }> = {
  both: { box: "fill-surface stroke-line", edge: "stroke-muted", head: "fill-muted" },
  cls: { box: "fill-cls-soft stroke-cls", edge: "stroke-cls", head: "fill-cls" },
  gen: { box: "fill-gen-soft stroke-gen", edge: "stroke-gen", head: "fill-gen" },
  ui: { box: "fill-ui-soft stroke-ui", edge: "stroke-ui", head: "fill-ui" },
};

export default function ArchitectureDiagram() {
  return (
    <figure className="w-full">
      <div className="overflow-x-auto">
        <svg
          viewBox="0 0 1040 400"
          className="min-w-[720px] w-full h-auto"
          role="img"
          aria-label="Architecture: practice rows and lexicon build an evidence base; new rows are extracted into facts, checked at their date and labelled; a template generator writes claims that are validated; both go to output.csv; the frontend sends rows to extraction and shows verdicts."
        >
          <defs>
            {(["both", "cls", "gen", "ui"] as Flow[]).map((f) => (
              <marker
                key={f}
                id={`arrow-${f}`}
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M0,0 L10,5 L0,10 z" className={FLOW_CLASS[f].head} />
              </marker>
            ))}
          </defs>
          {EDGES.map(([a, b, f]) => (
            <path
              key={a + b}
              d={path(byId[a], byId[b])}
              className={`${FLOW_CLASS[f].edge} fill-none`}
              strokeWidth={1.6}
              strokeDasharray={f === "ui" ? "5 4" : undefined}
              markerEnd={`url(#arrow-${f})`}
            />
          ))}
          {NODES.map((n) => (
            <g key={n.id}>
              <rect
                x={n.x}
                y={n.y}
                width={w(n)}
                height={H}
                rx={10}
                className={FLOW_CLASS[n.flow].box}
                strokeWidth={1.4}
              />
              <text x={n.x + 14} y={n.y + 24} className="fill-fg text-[14px] font-semibold">
                {n.title}
              </text>
              <text x={n.x + 14} y={n.y + 43} className="fill-muted text-[12px]">
                {n.sub}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <figcaption className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
        <Legend cls="bg-cls" label="Labelling rows" />
        <Legend cls="bg-gen" label="Writing new claims" />
        <Legend cls="bg-ui" label="This page (live)" />
        <Legend cls="bg-muted" label="Shared" />
      </figcaption>
    </figure>
  );
}

function Legend({ cls, label }: { cls: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-2.5 w-2.5 rounded-full ${cls}`} />
      {label}
    </span>
  );
}
