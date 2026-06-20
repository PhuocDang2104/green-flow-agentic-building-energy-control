"use client";

import { ReactNode } from "react";

export default function MetricCard({
  icon, value, children, accent = "green",
}: {
  icon: ReactNode;
  value: string;
  children: ReactNode;
  accent?: "green" | "warm" | "cyan";
}) {
  const ring =
    accent === "warm" ? "rgba(220,90,60,0.18)"
    : accent === "cyan" ? "rgba(22,166,199,0.16)"
    : "rgba(0,122,61,0.12)";
  const fg =
    accent === "warm" ? "#d4533a"
    : accent === "cyan" ? "var(--gf-cyan)"
    : "var(--gf-green)";
  return (
    <div className="gf-card flex items-start gap-3.5 px-4 py-3.5">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl"
            style={{ background: ring, color: fg as string }}>
        {icon}
      </span>
      <div className="min-w-0">
        <div className="text-[22px] font-semibold leading-tight"
             style={{ color: "var(--gf-ink)" }}>{value}</div>
        <p className="mt-0.5 text-[12.5px] leading-snug"
           style={{ color: "var(--gf-muted)" }}>{children}</p>
      </div>
    </div>
  );
}
