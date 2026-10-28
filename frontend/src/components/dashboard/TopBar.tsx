import { RefreshCw, Search } from "lucide-react";
import { cn } from "@/lib/utils";

export type HealthState = { state: "checking" } | { state: "ready"; demo: boolean } | { state: "down"; error: string };

export function TopBar({ query, onQuery, health, onRetry }: {
  query: string;
  onQuery: (q: string) => void;
  health: HealthState;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <label className="flex h-12 w-full items-center gap-3 rounded-full bg-card px-5 shadow-soft sm:max-w-sm">
        <Search className="size-4 text-muted-foreground" />
        <input
          value={query}
          onChange={(e) => onQuery(e.target.value)}
          placeholder="Search rows…"
          aria-label="Search rows"
          className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
      </label>
      <StatusPill health={health} onRetry={onRetry} />
    </div>
  );
}

function StatusPill({ health, onRetry }: { health: HealthState; onRetry: () => void }) {
  const base = "inline-flex items-center gap-2 self-start rounded-full px-4 py-2 text-xs font-semibold sm:self-auto";
  if (health.state === "checking")
    return (
      <span className={cn(base, "bg-muted text-muted-foreground")}>
        <span className="size-2 animate-pulse rounded-full bg-muted-foreground" />
        Checking the engine…
      </span>
    );
  if (health.state === "down")
    return (
      <button onClick={onRetry} title={health.error} className={cn(base, "bg-bad-soft text-bad")}>
        <span className="size-2 rounded-full bg-bad" />
        Engine API not reachable
        <RefreshCw className="size-3.5" />
      </button>
    );
  return (
    <span className={cn(base, health.demo ? "bg-warn-soft text-warn" : "bg-accent text-primary")}>
      <span className={cn("size-2 rounded-full", health.demo ? "bg-warn" : "animate-pulse bg-primary")} />
      {health.demo ? "Demo mode — simulated results" : "Live engine"}
    </span>
  );
}
