import { ReactNode } from "react";
import Skeleton from "@/components/shared/Skeleton";

const STATUS_DOT: Record<string, string> = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
  normal: "bg-teal",
};

export default function KpiCard({
  title, value, delta, status = "normal", icon, loading = false,
}: {
  title: string;
  value: string;
  delta?: string;
  status?: "success" | "warning" | "danger" | "info" | "normal";
  icon?: ReactNode;
  loading?: boolean;
}) {
  return (
    <div className="card flex flex-col gap-1 px-5 py-4">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-text-secondary">{title}</span>
        {icon ?? <span className={`h-2 w-2 rounded-full ${loading ? "bg-border" : STATUS_DOT[status]}`} />}
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
    </div>
  );
}
