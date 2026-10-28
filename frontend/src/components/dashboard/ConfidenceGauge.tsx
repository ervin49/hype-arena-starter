import { confFraction } from "@/lib/format";

const STROKE = 16;

// Semicircle gauge filled to the confidence: 0.65 fills 65% of the arc.
export function ConfidenceGauge({ confidence }: { confidence: number | null }) {
  const c = Math.PI * 80;
  const f = confFraction(confidence);
  // Rounded ends add STROKE/2 at each end of both the track and the fill, so
  // the track shows c + STROKE. Size the fill so it shows f of that, ends included.
  const dash = Math.max(0.01, f * (c + STROKE) - STROKE);
  return (
    <div className="relative mx-auto w-full max-w-[220px]">
      <svg viewBox="0 0 200 115" className="w-full" aria-hidden>
        <path d="M20,100 A80,80 0 0 1 180,100" fill="none" stroke="var(--track)" strokeWidth={STROKE} strokeLinecap="round" />
        <path
          d="M20,100 A80,80 0 0 1 180,100"
          fill="none"
          stroke="var(--primary)"
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c + STROKE}`}
          style={{ transition: "stroke-dasharray .6s ease" }}
          opacity={f === 0 ? 0 : 1}
        />
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center">
        <div className="text-3xl font-bold tabular-nums text-heading">{confidence == null ? "—" : `${Math.round(confidence * 100)}%`}</div>
        <div className="text-xs text-muted-foreground">confidence</div>
      </div>
    </div>
  );
}
