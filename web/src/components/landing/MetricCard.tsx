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
    <div className="gf-card flex items-start gap-3.5 px-4 py-3.5">
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl"
            style={{ background: "var(--gf-green-soft)", color: "var(--gf-green)" }}>
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
