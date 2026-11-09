import { cn, titleCase } from "@/lib/utils";

const tones: Record<string, string> = {
  verified: "bg-green-100 text-green-800",
  manual: "bg-blue-100 text-blue-800",
  flagged: "bg-amber-100 text-amber-900",
  rejected: "bg-red-100 text-red-800",
  not_marked: "bg-slate-100 text-slate-600",
  open: "bg-green-100 text-green-800",
  scheduled: "bg-sky-100 text-sky-800",
  closed: "bg-slate-200 text-slate-700",
  cancelled: "bg-red-100 text-red-800",
  neutral: "bg-slate-100 text-slate-700",
};

export function Badge({ value, label }: { value: string; label?: string }) {
  return (
    <span className={cn("inline-block rounded-full px-2.5 py-0.5 text-xs font-medium", tones[value] ?? tones.neutral)}>
      {label ?? titleCase(value)}
    </span>
  );
}
