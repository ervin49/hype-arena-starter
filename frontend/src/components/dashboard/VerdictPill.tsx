import type { Label } from "@/lib/types";
import { cn } from "@/lib/utils";

const STYLES: Record<Label, string> = {
  true: "bg-ok-soft text-ok",
  false: "bg-bad-soft text-bad",
  unsure: "bg-warn-soft text-warn",
};

export function VerdictPill({ label, className }: { label: Label; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold", STYLES[label], className)}>
      <span className="size-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}
