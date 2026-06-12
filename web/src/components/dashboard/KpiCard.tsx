import { ReactNode } from "react";

const STATUS_DOT: Record<string, string> = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
  normal: "bg-teal",
};

export default function KpiCard({
  title, value, delta, status = "normal", icon,
}: {
  title: string;
  value: string;
  delta?: string;
  status?: "success" | "warning" | "danger" | "info" | "normal";
  icon?: ReactNode;
}) {
  return (
    <div className="card flex flex-col gap-1 px-5 py-4">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium text-text-secondary">{title}</span>
        {icon ?? <span className={`h-2 w-2 rounded-full ${STATUS_DOT[status]}`} />}
      </div>
      <span className="text-[26px] font-semibold leading-tight tracking-tight">{value}</span>
      {delta && <span className="text-xs text-text-muted">{delta}</span>}
    </div>
  );
}
