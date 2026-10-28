"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, ListChecks, Moon, Network, Sun, Upload } from "lucide-react";
import { cn } from "@/lib/utils";

const ITEMS = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/", page: "/" },
  { icon: Upload, label: "Upload", href: "/#upload", page: null },
  { icon: ListChecks, label: "Results", href: "/#results", page: null },
  { icon: Network, label: "Architecture", href: "/architecture", page: "/architecture" },
];

const LINK = "grid size-11 place-items-center rounded-2xl transition";
const IDLE = "text-sidebar-foreground hover:bg-sidebar-accent hover:text-primary";
const ACTIVE = "bg-primary text-primary-foreground shadow-soft";

export function Sidebar() {
  const pathname = usePathname();
  const [dark, setDark] = useState(false);

  useEffect(() => setDark(document.documentElement.classList.contains("dark")), []);

  const toggleDark = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      // Storage may be blocked; the toggle still works for this visit.
    }
  };

  const links = ITEMS.map((it) => (
    <Link
      key={it.label}
      href={it.href}
      title={it.label}
      aria-label={it.label}
      aria-current={it.page === pathname ? "page" : undefined}
      className={cn(LINK, it.page === pathname ? ACTIVE : IDLE)}
    >
      <it.icon className="size-5" />
    </Link>
  ));
  const toggle = (
    <button onClick={toggleDark} aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} className={cn(LINK, IDLE)}>
      {dark ? <Sun className="size-5" /> : <Moon className="size-5" />}
    </button>
  );

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[72px] flex-col items-center gap-2 bg-sidebar py-6 shadow-soft md:flex">
        <div className="mb-6 grid size-11 place-items-center rounded-2xl bg-primary text-sm font-bold text-primary-foreground">TT</div>
        {links}
        <div className="mt-auto">{toggle}</div>
      </aside>
      <nav className="fixed inset-x-0 bottom-0 z-30 flex items-center justify-around bg-sidebar px-2 py-2 shadow-soft md:hidden">
        {links}
        {toggle}
      </nav>
    </>
  );
}
