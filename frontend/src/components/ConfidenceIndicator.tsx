interface ConfidenceIndicatorProps {
  value: number; // 0–1
  showBar?: boolean;
}

export function ConfidenceIndicator({
  value,
  showBar = true,
}: ConfidenceIndicatorProps) {
  const pct = Math.round(value * 100);
  const barColor =
    pct >= 80
      ? "bg-emerald-500"
      : pct >= 60
      ? "bg-amber-400"
      : "bg-slate-300";

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-500 w-8 text-right font-mono">{pct}%</span>
      {showBar && (
        <div
          className="h-1.5 w-16 rounded-full bg-slate-100 overflow-hidden"
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Confidence ${pct}%`}
        >
          <div
            className={`h-full rounded-full transition-all ${barColor}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  );
}
