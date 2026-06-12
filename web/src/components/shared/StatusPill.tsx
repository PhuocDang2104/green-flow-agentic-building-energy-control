const STYLES: Record<string, string> = {
  normal: "bg-teal-soft text-teal",
  success: "bg-green-50 text-success",
  executed: "bg-green-50 text-success",
  approved: "bg-green-50 text-success",
  auto_run: "bg-green-50 text-success",
  watch: "bg-amber-50 text-warning",
  warning: "bg-amber-50 text-warning",
  pending: "bg-amber-50 text-warning",
  pending_approval: "bg-amber-50 text-warning",
  approval_required: "bg-amber-50 text-warning",
  running: "bg-blue-50 text-info",
  info: "bg-blue-50 text-info",
  high: "bg-red-50 text-danger",
  danger: "bg-red-50 text-danger",
  failed: "bg-red-50 text-danger",
  rejected: "bg-red-50 text-danger",
  blocked: "bg-slate-100 text-text-secondary",
  empty: "bg-slate-100 text-text-secondary",
  completed: "bg-green-50 text-success",
  awaiting_approval: "bg-amber-50 text-warning",
};

export default function StatusPill({ status, label }: { status?: string | null; label?: string }) {
  const key = (status || "normal").toLowerCase();
  return (
    <span className={`pill ${STYLES[key] || "bg-slate-100 text-text-secondary"}`}>
      {label || (status || "–").replaceAll("_", " ")}
    </span>
  );
}
