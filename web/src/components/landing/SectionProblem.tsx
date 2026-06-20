"use client";

import { AlertTriangle, DatabaseZap, TrendingUp } from "lucide-react";

const SMALL = [
  { icon: <DatabaseZap size={18} />, text: "Too much data, not enough action" },
  { icon: <TrendingUp size={18} />, text: "Operating costs keep rising" },
  { icon: <AlertTriangle size={18} />, text: "Extreme weather puts occupants at risk" },
];

export default function SectionProblem() {
  return (
    <div className="gf-section" data-section="5">
      <div className="flex w-full max-w-4xl flex-col items-center text-center">
        <h2 data-reveal className="text-[clamp(28px,4.4vw,52px)] font-semibold leading-[1.08] tracking-tight"
            style={{ color: "var(--gf-ink)" }}>
          <span className="gf-line-mask"><span className="gf-line-inner">Data is everywhere.</span></span>
          <span className="gf-line-mask"><span className="gf-line-inner gf-em">Clear action is not.</span></span>
        </h2>

        <div data-reveal className="gf-card mt-8 w-full max-w-2xl p-6 text-left">
          <p className="mb-2 text-[13px] font-semibold" style={{ color: "var(--gf-green)" }}>
            Key Problem
          </p>
          <p className="text-[15px] leading-relaxed" style={{ color: "var(--gf-ink)" }}>
            Building owners and facility managers need a reliable way to reduce
            energy waste and operating costs while keeping occupants safe during
            extreme weather.
          </p>
        </div>

        <div className="mt-4 grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-3">
          {SMALL.map((s) => (
            <div key={s.text} data-reveal className="gf-card flex flex-col items-start gap-2.5 p-4 text-left">
              <span className="grid h-9 w-9 place-items-center rounded-xl"
                    style={{ background: "var(--gf-green-soft)", color: "var(--gf-green)" }}>
                {s.icon}
              </span>
              <span className="text-[13px] font-medium" style={{ color: "var(--gf-ink)" }}>
                {s.text}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
