import ArchitectureDiagram from "@/components/ArchitectureDiagram";
import Workbench from "@/components/Workbench";

export default function Home() {
  return (
    <main className="mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-6 sm:py-10">
      <header>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted">Git Happens · QA DNA — Hype or Truth</p>
        <h1 className="mt-1 text-2xl font-semibold sm:text-3xl">Temporal Truth Engine</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          Extracts the facts a sentence states, looks up what the Hooly universe said on that sentence&apos;s date, and
          explains each verdict. No LLM runs at runtime.
        </p>
      </header>

      <section className="rounded-2xl border border-line bg-surface p-5">
        <h2 className="mb-4 font-semibold">Architecture</h2>
        <ArchitectureDiagram />
      </section>

      <Workbench />
    </main>
  );
}
