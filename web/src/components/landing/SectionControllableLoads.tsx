"use client";

import { Fan, Flame, Lightbulb, Snowflake } from "lucide-react";
import FloatingChart from "./FloatingChart";

const LOADS = [
  { icon: <Lightbulb size={17} />, label: "Lighting" },
  { icon: <Flame size={17} />, label: "Heating" },
  { icon: <Fan size={17} />, label: "Ventilation" },
  { icon: <Snowflake size={17} />, label: "Air Condition" },
];

export default function SectionControllableLoads() {
  return (
    <div className="gf-section" data-section="2">
      <div className="grid w-full max-w-6xl items-center gap-10 lg:grid-cols-[1fr_1fr]">
        <div>
          <h2 data-reveal className="max-w-md text-[clamp(24px,3.4vw,40px)] font-semibold leading-[1.12] tracking-tight"
              style={{ color: "var(--gf-ink)" }}>
            Inside commercial buildings, the biggest energy loads come from{" "}
            <span className="gf-em">everyday operations.</span>
          </h2>
          <div data-reveal className="gf-card mt-7 max-w-sm p-5">
            <p className="mb-3 text-[13px] font-semibold" style={{ color: "var(--gf-green)" }}>
              Key controllable loads
            </p>
            <div className="grid grid-cols-2 gap-2.5">
              {LOADS.map((l) => (
                <div key={l.label}
                     className="flex items-center gap-2.5 rounded-xl px-3 py-2.5"
                     style={{ background: "var(--gf-green-soft)" }}>
                  <span style={{ color: "var(--gf-green)" }}>{l.icon}</span>
                  <span className="text-[13px] font-medium" style={{ color: "var(--gf-ink)" }}>
                    {l.label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="relative hidden h-[420px] lg:block" style={{ perspective: "1200px" }}>
          <FloatingChart src="/assets/landing/HVAC_light_pie.png" alt="HVAC and lighting energy share"
                         className="absolute right-6 top-2 w-[58%]" depth={1.4} tilt={-12} />
          <FloatingChart src="/assets/landing/HVAC_Lighting_bar.png" alt="HVAC and lighting bar chart"
                         className="absolute bottom-2 left-2 w-[56%]" depth={0.8} tilt={10} />
        </div>
      </div>
    </div>
  );
}
