type Flow = "cls" | "gen" | "ui" | "both";

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

const STROKE: Record<Flow, string> = {
  cls: "var(--primary)",
  gen: "var(--indigo)",
  ui: "var(--primary)",
  both: "var(--muted-foreground)",
};

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
    const x1 = a.x + w(a), y1 = a.y + H - 12, x2 = b.x + w(b) / 2, y2 = b.y;
    return `M ${x1} ${y1} C ${x2} ${y1}, ${x2} ${y1}, ${x2} ${y2}`;
  }
  const x1 = a.x + w(a), y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2;
  const dx = Math.max(24, (x2 - x1) / 2);
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
}

export function ArchitectureDiagram() {
  return (
    <div id="architecture" className="card-soft scroll-mt-6 p-5 sm:p-6">
      <h2 className="text-lg font-bold">Architecture</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Two flows share one evidence base: labelling rows at their date, and writing new claims. No LLM runs at runtime.
      </p>
      <div className="mt-4 overflow-x-auto">
        <svg
          viewBox="0 0 1040 400"
          className="h-auto w-full min-w-[720px]"
          role="img"
          aria-label="Architecture: practice rows and lexicon build an evidence base; new rows are extracted into facts, checked at their date and labelled; a template generator writes claims that are validated; both go to output.csv; the frontend sends rows to extraction and shows verdicts."
        >
          <defs>
            {(Object.keys(STROKE) as Flow[]).map((f) => (
              <marker key={f} id={`arrow-${f}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill={STROKE[f]} />
              </marker>
            ))}
          </defs>
          {EDGES.map(([a, b, f]) => (
            <path
              key={a + b}
              d={path(byId[a]!, byId[b]!)}
              fill="none"
              stroke={STROKE[f]}
              strokeWidth={1.8}
              strokeDasharray={f === "ui" ? "6 5" : undefined}
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
                rx={14}
                fill={n.flow === "both" ? "var(--card)" : "var(--accent)"}
                stroke={STROKE[n.flow]}
                strokeWidth={1.5}
                strokeDasharray={n.flow === "ui" ? "5 4" : undefined}
                style={{ filter: "drop-shadow(0 6px 12px var(--node-shadow))" }}
              />
              <text x={n.x + 14} y={n.y + 24} fontSize={14} fontWeight={600} fill="var(--heading)">
                {n.title}
              </text>
              <text x={n.x + 14} y={n.y + 43} fontSize={12} fill="var(--muted-foreground)">
                {n.sub}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-2"><span className="h-0.5 w-5 bg-primary" />Labelling rows</span>
        <span className="flex items-center gap-2"><span className="h-0.5 w-5 bg-indigo" />Writing new claims</span>
        <span className="flex items-center gap-2"><span className="w-5 border-t-2 border-dashed border-primary" />This page (live)</span>
        <span className="flex items-center gap-2"><span className="h-0.5 w-5 bg-muted-foreground" />Shared</span>
      </div>
    </div>
  );
}
