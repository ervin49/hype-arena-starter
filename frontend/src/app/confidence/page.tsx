import type { Metadata } from "next";
import { ConfidenceView } from "@/components/confidence/ConfidenceView";
import { StatusPill } from "@/components/dashboard/TopBar";
import { AppShell } from "@/components/dashboard/AppShell";

export const metadata: Metadata = {
  title: "Confidence — Temporal Truth Engine",
  description: "How often the system is right at each confidence it reports, for labels and for claims.",
};

export default function ConfidencePage() {
  return (
    <AppShell>
      <main className="min-w-0 flex-1 space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <header>
            <p className="text-xs font-semibold uppercase tracking-widest text-primary">Git Happens · QA DNA — Hype or Truth</p>
            <h1 className="mt-1 text-2xl font-bold sm:text-3xl">Confidence</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              A confidence should equal how often we are right. Measured on data the system did not learn from.
            </p>
          </header>
          <StatusPill />
        </div>
        <ConfidenceView />
      </main>
    </AppShell>
  );
}
