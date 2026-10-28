import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { ARIA_LABEL, EDGES, NODES, NODE_H, VIEW_H, STROKE, edgePath, nodeW, type Flow } from "@/lib/architecture";

export function ArchitectureDiagram() {
  return (
    <div id="architecture" className="card-soft scroll-mt-6 p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold">Architecture</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Two flows share one evidence base: labelling rows at their date, and writing new claims. No LLM runs at runtime.
          </p>
        </div>
        <Link href="/architecture" className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline">
          Watch the last run <ArrowRight className="size-4" />
        </Link>
      </div>
      <div className="mt-4 overflow-x-auto">
        <svg viewBox={`0 0 1040 ${VIEW_H}`} className="h-auto w-full min-w-[720px]" role="img" aria-label={ARIA_LABEL}>
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
              d={edgePath(a, b)}
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
                width={nodeW(n)}
                height={NODE_H}
                rx={14}
                fill={n.flow === "both" ? "var(--card)" : "var(--accent)"}
                stroke={STROKE[n.flow]}
                strokeWidth={1.5}
                strokeDasharray={n.flow === "ui" ? "5 4" : undefined}
                style={{ filter: "drop-shadow(0 6px 12px var(--node-shadow))" }}
              />
              <text x={n.x + 14} y={n.y + 23} fontSize={14} fontWeight={600} fill="var(--heading)">
                {n.title}
              </text>
              <text x={n.x + 14} y={n.y + 42} fontSize={11} fontWeight={600} fill="var(--primary)">
                {n.tech}
              </text>
              <text x={n.x + 14} y={n.y + 60} fontSize={12} fill="var(--muted-foreground)">
                {n.sub}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <ArchitectureLegend />
    </div>
  );
}

export function ArchitectureLegend() {
  return (
    <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground">
      <span className="flex items-center gap-2"><span className="h-0.5 w-5 bg-primary" />Labelling rows</span>
      <span className="flex items-center gap-2"><span className="h-0.5 w-5 bg-indigo" />Writing new claims</span>
      <span className="flex items-center gap-2"><span className="w-5 border-t-2 border-dashed border-primary" />This page (live)</span>
      <span className="flex items-center gap-2"><span className="h-0.5 w-5 bg-muted-foreground" />Shared</span>
    </div>
  );
}
