export function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

export function ProgressBar({ value, threshold }: { value: number | null; threshold?: number }) {
  const pct = value ?? 0;
  const ok = threshold === undefined || pct >= threshold;
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
      className="h-2 w-full overflow-hidden rounded-full bg-slate-200"
    >
      <div className={ok ? "h-full bg-green-500" : "h-full bg-amber-500"} style={{ width: `${Math.min(100, pct)}%` }} />
    </div>
  );
}
