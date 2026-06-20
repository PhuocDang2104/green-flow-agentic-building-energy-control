"use client";

import { BarChart3 } from "lucide-react";
import AnimatedNumber from "./AnimatedNumber";

export default function SectionHanoiBreakdown({ active }: { active: boolean }) {
  return (
    <div className="gf-section" data-section="3">
      <div className="grid w-full max-w-6xl items-center gap-10 lg:grid-cols-[1fr_0.9fr]">
        <div className="flex justify-center">
          <img
            data-pie
            src="/assets/landing/HVAC_light_pie.png"
            alt="Ha Noi commercial building energy breakdown — HVAC and lighting share"
            draggable={false}
            className="w-[96%] max-w-lg select-none"
            style={{
              objectFit: "contain",
              filter: "drop-shadow(0 34px 52px rgba(0,60,30,0.24))",
            }}
          />
        </div>
        <div data-reveal className="gf-card relative overflow-hidden p-7">
          <div className="absolute -right-6 top-6 hidden h-40 w-3 rounded-full sm:block"
               style={{ background: "linear-gradient(var(--gf-green), var(--gf-leaf))", opacity: 0.5 }} />
          <p className="max-w-xs text-[15px]" style={{ color: "var(--gf-muted)" }}>
            Zooming into Ha Noi commercial buildings, HVAC and lighting together represent
          </p>
          <div className="my-1 flex items-end gap-2">
            <span className="text-[clamp(64px,11vw,128px)] font-bold leading-none"
                  style={{ color: "var(--gf-green)" }}>
              <AnimatedNumber value={70} active={active} />%
            </span>
            <BarChart3 className="mb-4 opacity-30" size={34} style={{ color: "var(--gf-green)" }} />
          </div>
          <p className="text-[15px]" style={{ color: "var(--gf-muted)" }}>
            of end-use energy consumption.
          </p>
          {/* mini ghost bars */}
          <div className="mt-5 flex items-end gap-1.5 opacity-25">
            {[40, 70, 55, 88, 62, 75].map((h, i) => (
              <span key={i} className="w-4 rounded-t"
                    style={{ height: h, background: "var(--gf-green)" }} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
