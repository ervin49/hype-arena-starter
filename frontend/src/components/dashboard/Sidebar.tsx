"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, ListChecks, Network, Sparkles, Upload } from "lucide-react";
import { cn } from "@/lib/utils";

const ITEMS = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/", page: "/" },
  { icon: Upload, label: "Upload", href: "/#upload", page: null },
  { icon: ListChecks, label: "Results", href: "/#results", page: null },
  { icon: Sparkles, label: "Claims", href: "/claims", page: "/claims" },
  { icon: Network, label: "Architecture", href: "/architecture", page: "/architecture" },
];

const LINK = "grid size-11 place-items-center rounded-2xl transition";
const IDLE = "text-sidebar-foreground hover:bg-sidebar-accent hover:text-primary";
const ACTIVE = "bg-primary text-primary-foreground shadow-soft";

export function Sidebar() {
  const pathname = usePathname();
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

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[72px] flex-col items-center gap-2 bg-sidebar py-6 shadow-soft md:flex">
        <div className="mb-6 grid size-11 place-items-center rounded-2xl bg-primary text-sm font-bold text-primary-foreground">TT</div>
        {links}
      </aside>
      <nav className="fixed inset-x-0 bottom-0 z-30 flex items-center justify-around bg-sidebar px-2 py-2 shadow-soft md:hidden">
        {links}
      </nav>
    </>
  );
}
