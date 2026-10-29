import { Link, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import {
  Database,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  Network,
  Settings2,
  Sparkles,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import fixture from "@/data/metrics.json";
import practice from "@/data/practice.json";
import { api, getApiBase, pct, setApiBase, type LabelCalibration } from "@/lib/arena";
import { cn } from "@/lib/utils";
import { ease } from "./ui";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/run", label: "Live run", icon: FlaskConical },
  { to: "/architecture", label: "Architecture", icon: Network },
  { to: "/claims", label: "Claims", icon: Sparkles },
  { to: "/confidence", label: "Confidence", icon: Gauge },
  { to: "/dataset", label: "Dataset", icon: Database },
] as const;

export function useApiHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    retry: false,
    refetchInterval: 15000,
    enabled: typeof window !== "undefined",
  });
}

function ApiStatus() {
  const { data, isError, isLoading, refetch } = useApiHealth();
  const [open, setOpen] = useState(false);
  const [base, setBase] = useState("");
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setBase(getApiBase());
    setMounted(true);
  }, []);
  const state =
    !mounted || isLoading
      ? "checking"
      : isError
        ? "offline"
        : data?.demo_mode
          ? "demo engine"
          : "live engine";
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 font-mono text-xs transition-colors hover:bg-accent"
      >
        <span
          className={cn(
            "h-2 w-2 rounded-full",
            !mounted
              ? "bg-muted-foreground"
              : isError
                ? "bg-verdict-false"
                : isLoading
                  ? "bg-muted-foreground"
                  : "bg-verdict-true pulse-dot",
          )}
        />
        API · {state}
        <Settings2 className="h-3.5 w-3.5 text-muted-foreground" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.2, ease }}
            className="absolute right-0 z-50 mt-2 w-80 rounded-xl border border-border bg-popover p-4 shadow-2xl"
          >
            <div className="eyebrow mb-2">Engine endpoint</div>
            <input
              value={base}
              onChange={(e) => setBase(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-2 focus:ring-ring"
            />
            <p className="mt-2 text-xs text-muted-foreground">
              FastAPI from <span className="font-mono">api/main.py</span>, through this server's{" "}
              <span className="font-mono">/api</span> proxy. When it is unreachable, pages show an
              error, never made-up results.
            </p>
            <button
              onClick={() => {
                setApiBase(base);
                refetch();
                setOpen(false);
              }}
              className="mt-3 w-full rounded-md bg-primary py-2 text-xs font-medium text-primary-foreground transition hover:brightness-110"
            >
              Save & reconnect
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Measured on rows the model never saw (GET /metrics), not check.sh's rows it was trained on.
const ALWAYS_TRUE = practice.labels.true / practice.total;

export function Shell({ children }: { children: ReactNode }) {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const metrics = useQuery({
    queryKey: ["metrics"],
    queryFn: api.metrics,
    retry: false,
    enabled: typeof window !== "undefined",
  });
  const accuracy = (metrics.data?.labels ?? (fixture.labels as LabelCalibration)).accuracy;
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-sidebar-border bg-brand text-sidebar-foreground p-4 md:flex">
        <nav className="flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon }) => {
            const active = to === "/" ? path === "/" : path.startsWith(to);
            return (
              <Link
                key={to}
                to={to}
                className="relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm"
              >
                {active && (
                  <motion.span
                    layoutId="nav-active"
                    className="absolute inset-0 rounded-lg border border-sidebar-border bg-sidebar-accent"
                    transition={{ type: "spring", stiffness: 420, damping: 34 }}
                  />
                )}
                <Icon
                  className={cn(
                    "relative h-4 w-4",
                    active ? "text-sidebar-primary" : "text-sidebar-foreground/60",
                  )}
                />
                <span
                  className={cn(
                    "relative",
                    active ? "text-sidebar-primary" : "text-sidebar-foreground/70",
                  )}
                >
                  {label}
                </span>
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto rounded-lg border border-sidebar-border bg-sidebar-accent p-3">
          <div className="eyebrow text-sidebar-foreground/70">Right on unseen rows</div>
          <div className="mt-1 text-2xl font-semibold text-sidebar-primary">{pct(accuracy, 1)}</div>
          <div className="text-xs text-sidebar-foreground/70">
            out of fold · always 'true' {pct(ALWAYS_TRUE, 1)}
          </div>
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex h-14 items-center justify-between gap-4 border-b border-border bg-background/80 px-4 backdrop-blur-xl md:px-8">
          <nav className="flex gap-1 overflow-x-auto md:hidden">
            {NAV.map(({ to, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                className="rounded-md p-2 text-muted-foreground"
                activeProps={{ className: "text-primary" }}
                activeOptions={{ exact: to === "/" }}
              >
                <Icon className="h-4 w-4" />
              </Link>
            ))}
          </nav>
          <div className="hidden font-mono text-xs text-muted-foreground md:block">
            hooly / universe ·{" "}
            <span className="text-foreground">{path === "/" ? "overview" : path.slice(1)}</span>
          </div>
          <ApiStatus />
        </header>
        <motion.main
          key={path}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease }}
          className="bg-grid flex-1 px-4 py-8 md:px-8"
        >
          <div className="mx-auto max-w-7xl">{children}</div>
        </motion.main>
      </div>
    </div>
  );
}
