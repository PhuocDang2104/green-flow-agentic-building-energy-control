"use client";

import { ReactNode } from "react";

export default function MetricCard({
  icon, value, children,
}: {
  icon: ReactNode;
  value: string;
  children: ReactNode;
  accent?: "green" | "warm" | "cyan";
}) {
  // icons are unified to one brand green across the whole landing
  return (
    <div className="gf-card flex items-start gap-4 px-5 py-4">
      <span className="gf-metric-icon shrink-0" style={{ color: "var(--gf-green)" }}>
        {icon}
      </span>
      <div className="min-w-0">
        <div className="text-[24px] font-semibold leading-tight"
             style={{ color: "var(--gf-ink)" }}>{value}</div>
        <p className="mt-1 text-[13.5px] leading-snug"
           style={{ color: "var(--gf-muted)" }}>{children}</p>
      </div>
    </div>
  );
}
