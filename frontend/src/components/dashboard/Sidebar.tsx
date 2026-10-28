import { LayoutDashboard, ListChecks, Moon, Network, Sun, Upload } from "lucide-react";

const ITEMS = [
  { icon: LayoutDashboard, label: "Dashboard", href: "#top" },
  { icon: Upload, label: "Upload", href: "#upload" },
  { icon: ListChecks, label: "Results", href: "#results" },
  { icon: Network, label: "Architecture", href: "#architecture" },
];

const LINK = "grid size-11 place-items-center rounded-2xl text-sidebar-foreground transition hover:bg-sidebar-accent hover:text-primary";

export function Sidebar({ dark, onToggleDark }: { dark: boolean; onToggleDark: () => void }) {
  const toggle = (
    <button onClick={onToggleDark} aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} className={LINK}>
      {dark ? <Sun className="size-5" /> : <Moon className="size-5" />}
    </button>
  );
  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[72px] flex-col items-center gap-2 bg-sidebar py-6 shadow-soft md:flex">
        <div className="mb-6 grid size-11 place-items-center rounded-2xl bg-primary text-sm font-bold text-primary-foreground">TT</div>
        {ITEMS.map((it) => (
          <a key={it.label} href={it.href} title={it.label} aria-label={it.label} className={LINK}>
            <it.icon className="size-5" />
          </a>
        ))}
        <div className="mt-auto">{toggle}</div>
      </aside>
      <nav className="fixed inset-x-0 bottom-0 z-30 flex items-center justify-around bg-sidebar px-2 py-2 shadow-soft md:hidden">
        {ITEMS.map((it) => (
          <a key={it.label} href={it.href} aria-label={it.label} className={LINK}>
            <it.icon className="size-5" />
          </a>
        ))}
        {toggle}
      </nav>
    </>
  );
}
