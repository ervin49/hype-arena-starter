import { animate, motion, useInView, useMotionValue, useTransform } from "motion/react";
import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { Label } from "@/lib/arena";

export const ease = [0.22, 1, 0.36, 1] as const;

export function Reveal({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function Counter({ value, decimals = 0, suffix = "" }: { value: number; decimals?: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) =>
    v.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + suffix,
  );
  useEffect(() => {
    if (inView) {
      const c = animate(mv, value, { duration: 1.4, ease });
      return () => c.stop();
    }
    return undefined;
  }, [inView, value, mv]);
  return <motion.span ref={ref} className="tabular-nums">{text}</motion.span>;
}

export function PageHeader({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <Reveal className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow && <div className="eyebrow mb-2">{eyebrow}</div>}
        <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">{title}</h1>
      </div>
      {children}
    </Reveal>
  );
}

export function Panel({ title, hint, children, className, action }: { title?: string; hint?: string; children: ReactNode; className?: string; action?: ReactNode }) {
  return (
    <div className={cn("panel p-5", className)}>
      {title && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-medium">{title}</h3>
            {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}

const pill: Record<Label, string> = {
  true: "bg-verdict-true/12 text-verdict-true border-verdict-true/30",
  false: "bg-verdict-false/12 text-verdict-false border-verdict-false/30",
  unsure: "bg-verdict-unsure/12 text-verdict-unsure border-verdict-unsure/30",
};
export function VerdictPill({ label }: { label: Label }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider", pill[label])}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}

export function ConfBar({ value }: { value: number | null }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
        <motion.div
          className="h-full rounded-full bg-primary"
          initial={{ width: 0 }}
          animate={{ width: `${(value ?? 0) * 100}%` }}
          transition={{ duration: 0.9, ease }}
        />
      </div>
      <span className="font-mono text-xs tabular-nums text-muted-foreground">
        {value == null ? "—" : value.toFixed(2)}
      </span>
    </div>
  );
}
