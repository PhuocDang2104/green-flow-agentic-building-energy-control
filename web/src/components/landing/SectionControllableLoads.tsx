"use client";

import { Fan, Flame, Lightbulb, Snowflake } from "lucide-react";
import BuildingStage from "./BuildingStage";

const LOADS = [
  { icon: <Lightbulb size={14} />, label: "Lighting" },
  { icon: <Flame size={14} />, label: "Heating" },
  { icon: <Fan size={14} />, label: "Ventilation" },
  { icon: <Snowflake size={14} />, label: "Air Condition" },
];

export default function SectionControllableLoads({
  active, themeMix,
}: { active: boolean; themeMix: number }) {
  return (
    <div className="gf-section" data-section="2">
      <div className="relative mx-auto w-full max-w-6xl" style={{ height: "80vh" }}>
        {/* headline */}
        <div data-reveal className="absolute left-1/2 top-0 z-30 w-full max-w-3xl -translate-x-1/2 text-center">
          <p className="mb-2 text-[13px] font-semibold tracking-wide" style={{ color: "var(--gf-green)" }}>
            INSIDE THE BUILDING
          </p>
          <h2 className="mx-auto max-w-2xl text-[clamp(22px,3.2vw,38px)] font-semibold leading-[1.12] tracking-tight"
              style={{ color: "var(--gf-ink)" }}>
            The biggest energy loads come from{" "}
            <span className="gf-em">everyday operations.</span>
          </h2>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {LOADS.map((l) => (
              <span key={l.label}
                    className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-medium"
                    style={{ background: "var(--gf-green-soft)", color: "var(--gf-ink)" }}>
                <span style={{ color: "var(--gf-green)" }}>{l.icon}</span>{l.label}
              </span>
            ))}
          </div>
        </div>

        {/* pie chart — left, behind (flies to section 3 on scroll) */}
        <img
          data-pie
          src="/assets/landing/HVAC_light_pie.png"
          alt="Energy share by end use — HVAC 48%, Lighting 22%"
          draggable={false}
          className="absolute left-[0%] top-[26%] z-10 w-[40%] max-w-[440px] select-none"
          style={{ filter: "drop-shadow(0 26px 40px rgba(0,60,30,0.22))" }}
        />

        {/* bar chart — right, behind */}
        <img
          data-reveal
          src="/assets/landing/HVAC_Lighting_bar.png"
          alt="Hanoi commercial buildings vs Asia benchmark by end use"
          draggable={false}
          className="absolute right-[-1%] top-[20%] z-10 w-[52%] max-w-[560px] select-none"
          style={{ filter: "drop-shadow(0 26px 40px rgba(0,60,30,0.18))" }}
        />

        {/* digital-twin building — centre, in front, rises up */}
        <div className="absolute bottom-[2%] left-1/2 z-20 h-[56%] w-[50%] max-w-[600px] -translate-x-1/2">
          {active && <BuildingStage themeMix={themeMix} />}
        </div>
      </div>
    </div>
  );
}
