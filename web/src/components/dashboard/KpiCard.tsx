import { ReactNode, useId } from "react";
import { CircleHelp } from "lucide-react";
import Skeleton from "@/components/shared/Skeleton";
import type { StatusTone } from "@/lib/healthBands";

const STATUS_DOT: Record<string, string> = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
  normal: "bg-teal",
};

const STATUS_BADGE: Record<string, string> = {
  success: "bg-green-50 text-success",
  warning: "bg-amber-50 text-amber-700",
  danger: "bg-red-50 text-danger",
  info: "bg-blue-50 text-info",
  normal: "bg-slate-100 text-text-secondary",
};

export interface KpiHelp {
  summary: string;
  statusReason: string;
  thresholds: string;
  timestamp?: string;
}

export default function KpiCard({
  title, value, delta, status = "normal", statusLabel, help, icon, loading = false,
}: {
  title: string;
  value: string;
  delta?: string;
  status?: StatusTone;
  statusLabel?: string;
  help?: KpiHelp;
  icon?: ReactNode;
  loading?: boolean;
}) {
  const tooltipId = useId();
  return (
    <div className="card group relative flex flex-col gap-1 px-5 py-4 outline-none transition hover:z-30 hover:border-teal/25 focus:z-30 focus:border-teal/40 focus:ring-2 focus:ring-teal/10"
         tabIndex={help ? 0 : undefined} aria-describedby={help ? tooltipId : undefined}>
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-[13px] font-medium text-text-secondary">
          {title}
          {help && <CircleHelp size={13} className="text-text-muted/80 transition group-hover:text-teal" aria-hidden />}
        </span>
        <span className="flex items-center gap-1.5">
          {statusLabel && !loading && (
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${STATUS_BADGE[status]}`}>
              {statusLabel}
            </span>
          )}
          {icon ?? (!statusLabel && <span className={`h-2 w-2 rounded-full ${loading ? "bg-border" : STATUS_DOT[status]}`} />)}
        </span>
      </div>
      {loading ? (
        <>
          <Skeleton className="mt-1 h-7 w-24" />
          <Skeleton className="mt-1.5 h-3 w-20" />
        </>
      ) : (
        <>
          <span className="animate-fade-in text-[26px] font-semibold leading-tight tracking-tight">{value}</span>
          {delta && <span className="text-xs text-text-muted">{delta}</span>}
        </>
      )}
      {help && (
        <div id={tooltipId} role="tooltip"
             className="invisible pointer-events-none absolute left-3 right-3 top-[calc(100%-3px)] z-40 translate-y-1 rounded-xl border border-slate-200 bg-slate-900 px-3 py-2.5 text-left opacity-0 shadow-xl transition duration-150 group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 group-focus:visible group-focus:translate-y-0 group-focus:opacity-100">
          <p className="text-[11.5px] font-semibold text-white">What this means</p>
          <p className="mt-1 text-[11px] leading-relaxed text-slate-200">{help.summary}</p>
          <p className="mt-2 border-t border-white/10 pt-2 text-[11px] leading-relaxed text-white">
            {help.statusReason}
          </p>
          <p className="mt-1 text-[10px] leading-relaxed text-slate-400">{help.thresholds}</p>
          {help.timestamp && <p className="mt-1.5 text-[10px] text-slate-400">Updated {help.timestamp}</p>}
        </div>
      )}
    </div>
  );
}
