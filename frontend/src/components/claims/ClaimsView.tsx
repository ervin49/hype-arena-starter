"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Loader2, MousePointerClick } from "lucide-react";
import { EngineError, getClaims, type EngineFailure } from "@/lib/api";
import { confFraction } from "@/lib/format";
import type { Claim, ClaimType, ClaimsResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { VerdictPill } from "@/components/dashboard/VerdictPill";

type Filter = "all" | ClaimType;

const TYPES: ClaimType[] = ["fact", "compare", "change", "at_event", "relation"];
const PAGE = 25;
const TYPE_HELP: Record<ClaimType, string> = {
  fact: "a fact's value on 29 Oct 2026",
  compare: "two facts compared on 29 Oct 2026",
  change: "a value that later changed to another",
  at_event: "a value on the date of an event",
  relation: "a fact of the entity a link names",
};

// The claims the batch run writes to output.csv, as the API built them at startup.
export function ClaimsView() {
  const [data, setData] = useState<ClaimsResponse | null>(null);
  const [error, setError] = useState<EngineFailure | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(PAGE);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    getClaims().then(setData, (e) =>
      setError({ message: e instanceof Error ? e.message : "The API failed.", detail: e instanceof EngineError ? e.detail : undefined }),
    );
  }, []);

  const claims = useMemo(() => data?.claims ?? [], [data]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return claims.filter((c) => (filter === "all" || c.type === filter) && (!q || c.text.toLowerCase().includes(q)));
  }, [claims, filter, query]);
  const selected = claims.find((c) => c.id === selectedId) ?? null;
  const count = (f: Filter) => (f === "all" ? claims.length : claims.filter((c) => c.type === f).length);

  if (error)
    return (
      <div role="alert" className="card-soft flex gap-3 bg-bad-soft p-5 text-bad">
        <AlertTriangle className="mt-0.5 size-5 shrink-0" />
        <div>
          <p className="font-semibold">The claims could not be loaded: {error.message}</p>
          {error.detail && <p className="mt-1 break-words font-mono text-xs">{error.detail}</p>}
        </div>
      </div>
    );
  if (!data)
    return (
      <p className="card-soft flex items-center gap-2 p-5 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> Loading the claims…
      </p>
    );
  if (claims.length === 0)
    return (
      <p className="card-soft p-5 text-sm text-muted-foreground">
        No claims: {data.demo_mode ? "this frontend runs in demo mode, which has no claim fixture." : "the API built none."}
      </p>
    );

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="card-soft p-5 sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-lg font-bold">{claims.length.toLocaleString("en-US")} generated claims</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Every one validated against the schema, the lexicon, the claim-form rules and its evidence; all labelled true.
            </p>
          </div>
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setShown(PAGE);
            }}
            placeholder="Search claims…"
            aria-label="Search claims"
            className="h-9 w-full rounded-full border bg-card px-4 text-sm outline-none focus:border-primary sm:w-56"
          />
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {(["all", ...TYPES] as Filter[]).map((f) => (
            <button
              key={f}
              onClick={() => {
                setFilter(f);
                setShown(PAGE);
              }}
              title={f === "all" ? undefined : TYPE_HELP[f]}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-semibold transition",
                f === filter ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:text-primary",
              )}
            >
              {f === "all" ? "All" : f.replace("_", " ")} <span className="tabular-nums opacity-70">{count(f)}</span>
            </button>
          ))}
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr>
                <th className="pb-2 font-medium">Claim</th>
                <th className="pb-2 font-medium">Type</th>
                <th className="pb-2 font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, shown).map((c) => (
                <tr
                  key={c.id}
                  onClick={() => setSelectedId(c.id)}
                  className={cn("cursor-pointer border-t transition hover:bg-muted/60", selectedId === c.id && "bg-accent")}
                >
                  <td className="max-w-md py-3 pr-4">
                    <div className="font-mono text-[11px] text-muted-foreground">{c.id}</div>
                    <div className="font-medium text-heading">{c.text}</div>
                  </td>
                  <td className="whitespace-nowrap py-3 pr-4">
                    <span className="rounded-full bg-accent px-2.5 py-0.5 text-xs font-semibold text-primary">{c.type.replace("_", " ")}</span>
                  </td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-track">
                        <div className="h-full rounded-full bg-primary" style={{ width: `${confFraction(c.confidence) * 100}%` }} />
                      </div>
                      <span className="text-xs font-semibold tabular-nums">{c.confidence.toFixed(2)}</span>
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={3} className="py-8 text-center text-muted-foreground">
                    No claims match.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {filtered.length > shown && (
          <button onClick={() => setShown((s) => s + PAGE * 4)} className="mt-4 text-sm font-semibold text-primary hover:underline">
            Show more ({(filtered.length - shown).toLocaleString("en-US")} left)
          </button>
        )}
      </div>
      <ClaimDetail claim={selected} />
    </div>
  );
}

function ClaimDetail({ claim }: { claim: Claim | null }) {
  if (!claim)
    return (
      <div className="card-soft flex flex-col items-center gap-3 self-start p-8 text-center text-sm text-muted-foreground">
        <span className="grid size-12 place-items-center rounded-2xl bg-accent text-primary">
          <MousePointerClick className="size-5" />
        </span>
        Select a claim to see its evidence.
      </div>
    );
  return (
    <div className="card-soft space-y-5 self-start p-6">
      <div>
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-sm font-bold text-heading">{claim.id}</span>
          <span className="rounded-full bg-accent px-2.5 py-0.5 text-xs font-semibold text-primary">{claim.type.replace("_", " ")}</span>
        </div>
        <p className="mt-3 text-sm font-medium leading-relaxed text-heading">“{claim.text}”</p>
        <p className="mt-2 text-xs text-muted-foreground">
          {TYPE_HELP[claim.type]} · confidence {claim.confidence.toFixed(2)}
        </p>
      </div>
      <section>
        <h3 className="text-sm font-bold">Form (JSON, as in output.csv)</h3>
        <pre className="mt-2 max-h-56 overflow-auto rounded-2xl bg-muted p-3 font-mono text-[11px]">{JSON.stringify(claim.form, null, 2)}</pre>
      </section>
      <section>
        <h3 className="text-sm font-bold">Evidence ({claim.evidence.length})</h3>
        <div className="mt-2 space-y-2">
          {claim.evidence.map((e) => (
            <div key={e.id} className="rounded-2xl bg-muted p-3 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono font-bold text-heading">{e.id}</span>
                <span className="flex items-center gap-2 tabular-nums text-muted-foreground">
                  {e.date}
                  {e.label && <VerdictPill label={e.label} />}
                </span>
              </div>
              <p className="mt-1 text-muted-foreground">{e.text}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
