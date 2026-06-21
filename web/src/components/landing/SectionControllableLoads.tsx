"use client";

import { Fan, Flame, Lightbulb, Snowflake, Zap } from "lucide-react";
import ChartCard from "./ChartCard";

const LOADS = [
  { icon: <Lightbulb size={17} />, label: "Lighting" },
  { icon: <Flame size={17} />, label: "Heating" },
  { icon: <Fan size={17} />, label: "Ventilation" },
  { icon: <Snowflake size={17} />, label: "Air Condition" },
];

export default function SectionControllableLoads() {
  return (
    <div className="gf-section" data-section="2">
      <div className="grid w-full max-w-6xl items-center gap-10 lg:grid-cols-[0.92fr_1.08fr]">
        {/* LEFT — headline + key controllable loads */}
        <div>
          <h2 data-reveal className="max-w-md text-[clamp(24px,3.4vw,40px)] font-semibold leading-[1.14] tracking-tight"
              style={{ color: "var(--gf-ink)" }}>
            Inside commercial buildings, the biggest energy loads come from{" "}
            <span className="gf-em">everyday operations.</span>
          </h2>

          <div data-reveal className="gf-card mt-7 max-w-md p-5">
            <div className="mb-4 flex items-center gap-2.5">
              <span className="grid h-9 w-9 place-items-center rounded-xl"
                    style={{ background: "var(--gf-green-soft)", color: "var(--gf-green)" }}>
                <Zap size={18} />
              </span>
              <p className="text-[15px] font-semibold" style={{ color: "var(--gf-green)" }}>
                Key controllable loads
              </p>
            </div>
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

        {/* RIGHT — pie (upper-right) + bar (lower-left, overlapping in front) */}
        <div data-reveal className="relative hidden lg:block">
          <ChartCard
            src="/assets/landing/HVAC_light_pie.png"
            alt="Energy share by end use — HVAC 48%, Lighting 22%"
            title="End-use energy share"
            caption="Hanoi commercial buildings"
            stats={[
              { label: "HVAC", value: "48%" },
              { label: "Lighting", value: "22%" },
              { label: "Office equipment", value: "12%" },
              { label: "Other loads", value: "18%" },
            ]}
            className="ml-auto w-[62%]"
            popupClass="left-[0%] top-[24%]"
          />
          <ChartCard
            src="/assets/landing/HVAC_Lighting_bar.png"
            alt="Hanoi commercial buildings vs Asia benchmark by end use"
            title="Hanoi vs Asia benchmark"
            caption="Share of end-use energy (Hanoi / Asia)"
            stats={[
              { label: "HVAC", value: "48% / 45%" },
              { label: "Lighting", value: "22% / 20%" },
              { label: "Equipment", value: "12% / 16%" },
              { label: "Vertical transport", value: "8% / 9%" },
            ]}
            className="z-[2] -mt-[20%] w-[60%]"
            popupClass="right-[2%] top-[6%]"
          />
        </div>
      </div>
    </div>
  );
}
