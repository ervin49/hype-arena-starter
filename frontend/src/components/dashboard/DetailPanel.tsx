import { useState } from "react";
import { AlertOctagon, CheckCircle2, CircleDashed, MousePointerClick } from "lucide-react";
import type { InputRow, Prediction } from "@/lib/types";
import { formatValue } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ConfidenceGauge } from "./ConfidenceGauge";
import { VerdictPill } from "./VerdictPill";

export function DetailPanel({ row, pred, rowsById }: { row?: InputRow; pred?: Prediction; rowsById: Map<string, InputRow> }) {
  const [raw, setRaw] = useState(false);
  if (!row || !pred) {
    return (
      <div className="card-soft flex flex-col items-center gap-3 p-8 text-center text-sm text-muted-foreground">
        <span className="grid size-12 place-items-center rounded-2xl bg-accent text-primary">
          <MousePointerClick className="size-5" />
        </span>
        Select a row to see why the engine decided.
      </div>
    );
  }
  const ex = pred.extraction;
  return (
    <div className="card-soft space-y-6 p-6">
      <div>
        <div className="font-mono text-sm font-bold text-heading">{row.id}</div>
        <div className="text-xs text-muted-foreground">checked at {row.date}</div>
        <p className="mt-3 text-sm font-medium leading-relaxed text-heading">“{row.text}”</p>
      </div>
      <ConfidenceGauge confidence={pred.confidence} />
      <div className="flex justify-center">
        <VerdictPill label={pred.label} className="px-4 py-1 text-sm" />
      </div>
      {pred.error && (
        <div role="alert" className="flex gap-2 rounded-2xl bg-bad-soft p-3 text-sm text-bad">
          <AlertOctagon className="mt-0.5 size-4 shrink-0" />
          <span className="break-words">The engine failed on this row: {pred.error}</span>
        </div>
      )}
      <section>
        <h3 className="text-sm font-bold">Why</h3>
        <p className="mt-1 text-sm text-muted-foreground">{pred.reason || "No reason given."}</p>
      </section>
      <section>
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold">Extracted facts</h3>
          {ex && (
            <div className="flex rounded-full bg-muted p-0.5 text-xs font-semibold">
              {["Table", "JSON"].map((t, i) => (
                <button
                  key={t}
                  onClick={() => setRaw(i === 1)}
                  className={cn("rounded-full px-2.5 py-0.5", raw === (i === 1) ? "bg-card text-primary shadow-soft" : "text-muted-foreground")}
                >
                  {t}
                </button>
              ))}
            </div>
          )}
        </div>
        {!ex ? (
          <p className="mt-2 text-xs text-muted-foreground">The API sent no extraction for this row.</p>
        ) : raw ? (
          <pre className="mt-2 max-h-56 overflow-auto rounded-2xl bg-muted p-3 font-mono text-[11px]">{JSON.stringify(ex, null, 2)}</pre>
        ) : ex.facts.length ? (
          <table className="mt-2 w-full text-xs">
            <thead className="text-muted-foreground">
              <tr>
                <th className="py-1 text-left font-medium">Subject</th>
                <th className="text-left font-medium">Attribute</th>
                <th className="text-left font-medium">Value</th>
              </tr>
            </thead>
            <tbody>
              {ex.facts.map((f, i) => (
                <tr key={i} className="border-t align-top">
                  <td className="py-1.5 pr-2 font-medium text-heading">{f.subject}</td>
                  <td className="py-1.5 pr-2 font-mono text-[11px]">{f.attribute}</td>
                  <td className="py-1.5 font-semibold text-primary">{formatValue(f.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="mt-2 text-xs text-muted-foreground">No facts extracted.</p>
        )}
        {ex && (
          <div className="mt-3 text-xs">
            <div className={cn("flex items-center gap-1.5 font-semibold", ex.complete ? "text-ok" : "text-warn")}>
              {ex.complete ? <CheckCircle2 className="size-3.5" /> : <CircleDashed className="size-3.5" />}
              Extraction {ex.complete ? "complete" : "incomplete"}
            </div>
            {ex.issues.length > 0 && (
              <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                {ex.issues.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>
      <section>
        <h3 className="text-sm font-bold">Evidence ({pred.evidence_ids.length})</h3>
        {pred.evidence_ids.length === 0 && <p className="mt-1 text-xs text-muted-foreground">No evidence cited.</p>}
        <div className="mt-2 space-y-2">
          {pred.evidence_ids.map((id) => {
            // A row of the upload, or a practice row the API sent with its text.
            const src = rowsById.get(id) ?? pred.evidence?.find((e) => e.id === id);
            return (
              <div key={id} className="rounded-2xl bg-muted p-3 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono font-bold text-heading">{id}</span>
                  {src && (
                    <span className="flex items-center gap-2 tabular-nums text-muted-foreground">
                      {src.date}
                      {src.label && <VerdictPill label={src.label} />}
                    </span>
                  )}
                </div>
                <p className="mt-1 text-muted-foreground">{src ? src.text : "The API sent no text for this source row."}</p>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
