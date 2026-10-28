import { Sidebar } from "./Sidebar";

// Page frame shared by every tab: the icon sidebar and the content area.
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div id="top" className="min-h-screen bg-background">
      <Sidebar />
      <div className="flex flex-col gap-6 px-4 pb-24 pt-5 sm:px-6 md:pb-8 md:pl-[96px] xl:flex-row">{children}</div>
    </div>
  );
}
