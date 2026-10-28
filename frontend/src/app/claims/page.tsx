import type { Metadata } from "next";
import { ClaimsView } from "@/components/claims/ClaimsView";
import { StatusPill } from "@/components/dashboard/TopBar";
import { AppShell } from "@/components/dashboard/AppShell";

export const metadata: Metadata = {
  title: "Claims — Temporal Truth Engine",
  description: "The new claims the system writes, each with its evidence.",
};

export default function ClaimsPage() {
  return (
    <AppShell>
      <main className="min-w-0 flex-1 space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <header>
            <p className="text-xs font-semibold uppercase tracking-widest text-primary">Git Happens · QA DNA — Hype or Truth</p>
            <h1 className="mt-1 text-2xl font-bold sm:text-3xl">Generated claims</h1>
            <p className="mt-1 text-sm text-muted-foreground">The new true claims the batch run writes to output.csv, built from the evidence base</p>
          </header>
          <StatusPill />
        </div>
        <ClaimsView />
      </main>
    </AppShell>
  );
}
