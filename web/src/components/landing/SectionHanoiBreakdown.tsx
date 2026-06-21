"use client";

import AnimatedNumber from "./AnimatedNumber";

export default function SectionHanoiBreakdown({ active }: { active: boolean }) {
  return (
    <div className="gf-section" data-section="3">
      <div className="grid w-full max-w-6xl items-center gap-10 lg:grid-cols-[1fr_0.9fr]">
        <div data-reveal className="flex min-h-[430px] justify-center">
          <img
            src="/assets/landing/HVAC_light_pie.png"
            alt="Ha Noi commercial building energy breakdown - HVAC and lighting share"
            draggable={false}
            className="w-[92%] max-w-lg select-none lg:hidden"
            style={{
              objectFit: "contain",
              filter: "drop-shadow(0 24px 38px rgba(0,60,30,0.18))",
            }}
          />
        </div>
        <div data-reveal className="gf-card gf-insight-card relative max-w-xl overflow-hidden p-8 sm:p-9">
          <div className="gf-insight-sheen" aria-hidden />
          <p className="relative max-w-md text-[17px] leading-8" style={{ color: "var(--gf-muted)" }}>
            Zooming into Ha Noi commercial buildings, HVAC and lighting together represent
          </p>
          <div className="relative mt-7 flex items-end gap-5">
            <span
              className="text-[92px] font-bold leading-none sm:text-[108px] lg:text-[116px]"
              style={{ color: "var(--gf-green)" }}
            >
              <AnimatedNumber value={70} active={active} />%
            </span>
          </div>
          <p className="relative mt-3 text-[17px]" style={{ color: "var(--gf-muted)" }}>
            of end-use energy consumption.
          </p>
        </div>
      </div>
    </div>
  );
}
