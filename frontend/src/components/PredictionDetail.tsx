import { useState } from "react";
import { formatValue } from "@/lib/format";
import type { InputRow, Prediction } from "@/lib/types";
import { ConfidenceBar, VerdictBadge } from "./Verdict";

interface Props {
  row: InputRow;
  prediction: Prediction;
  rowsById: Map<string, InputRow>;
}

export default function PredictionDetail({ row, prediction, rowsById }: Props) {
  const [raw, setRaw] = useState(false);
  const ex = prediction.extraction;

  return (
    <div className="space-y-5">
      <div>
        <div className="mb-1 flex items-center gap-2 text-xs text-muted">
          <span className="font-mono">{row.id}</span>
          <span>·</span>
          <span>checked at {row.date}</span>
        </div>
        <p className="text-[15px] leading-snug">{row.text}</p>
      </div>

      <div className="flex items-center gap-4">
        <VerdictBadge label={prediction.label} />
        <ConfidenceBar value={prediction.confidence} />
      </div>

      {prediction.error && (
        <p role="alert" className="rounded-lg bg-bad-soft p-2.5 text-sm text-bad">
          The engine failed on this row: {prediction.error}
        </p>
      )}

      <Section title="Why">
        <p className="text-sm">{prediction.reason || <span className="text-muted">No reason given.</span>}</p>
      </Section>

      <Section
        title="Extracted facts"
        aside={
          ex && (
            <button className="text-xs text-muted underline-offset-2 hover:underline" onClick={() => setRaw((r) => !r)}>
              {raw ? "table" : "JSON"}
            </button>
          )
        }
      >
        {!ex ? (
          <p className="text-sm text-muted">The API sent no extraction for this row.</p>
        ) : raw ? (
          <pre className="max-h-64 overflow-auto rounded-lg bg-bg p-3 font-mono text-xs">{JSON.stringify(ex, null, 2)}</pre>
        ) : (
          <>
            {ex.facts.length === 0 ? (
              <p className="text-sm text-muted">No facts extracted.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted">
                  <tr>
                    <th className="pb-1 font-normal">Subject</th>
                    <th className="pb-1 font-normal">Attribute</th>
                    <th className="pb-1 font-normal">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {ex.facts.map((f, i) => (
                    <tr key={i} className="border-t border-line align-top">
                      <td className="py-1.5 pr-2">{f.subject}</td>
                      <td className="py-1.5 pr-2 font-mono text-xs">{f.attribute}</td>
                      <td className="py-1.5">{formatValue(f.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="mt-2 text-xs text-muted">
              Extraction {ex.complete ? "complete" : <span className="text-warn">incomplete</span>}
              {ex.issues.length > 0 && <> · {ex.issues.join("; ")}</>}
            </p>
          </>
        )}
      </Section>

      <Section title={`Evidence (${prediction.evidence_ids.length})`}>
        {prediction.evidence_ids.length === 0 ? (
          <p className="text-sm text-muted">No evidence cited.</p>
        ) : (
          <ul className="space-y-2">
            {prediction.evidence_ids.map((id) => {
              const src = rowsById.get(id);
              return (
                <li key={id} className="rounded-lg border border-line p-2.5 text-sm">
                  <div className="mb-0.5 flex items-center gap-2 text-xs text-muted">
                    <span className="font-mono">{id}</span>
                    {src && (
                      <>
                        <span>·</span>
                        <span>{src.date}</span>
                        {src.label && <VerdictBadge label={src.label} />}
                      </>
                    )}
                  </div>
                  {src ? src.text : <span className="text-muted">Source row not in the uploaded file.</span>}
                </li>
              );
            })}
          </ul>
        )}
      </Section>
    </div>
  );
}

function Section({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section>
      <div className="mb-1.5 flex items-baseline justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  );
}
