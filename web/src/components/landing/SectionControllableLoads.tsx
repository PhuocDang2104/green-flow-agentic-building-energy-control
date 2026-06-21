"use client";

import { Fan, Flame, Lightbulb, Snowflake, Zap } from "lucide-react";
import ChartCard from "./ChartCard";

const LOADS = [
  { icon: <Lightbulb size={48} strokeWidth={1.6} />, label: "Lighting" },
  { icon: <Flame size={48} strokeWidth={1.6} />, label: "Heating" },
  { icon: <Fan size={48} strokeWidth={1.6} />, label: "Ventilation" },
  { icon: <Snowflake size={48} strokeWidth={1.6} />, label: "Air Condition" },
];

export default function SectionControllableLoads() {
  return (
    <div className="gf-section" data-section="2">
      <div className="gf-loads-layout grid w-full max-w-7xl items-center gap-12 lg:grid-cols-[0.86fr_1.14fr]">
        <div className="gf-loads-copy">
          <h2
            data-reveal
            className="max-w-[640px] text-[26px] leading-[1.24] sm:text-[29px] lg:text-[30px]"
            style={{ color: "var(--gf-ink)" }}
          >
            Inside commercial buildings, the biggest energy loads come from{" "}
            <span className="gf-em">everyday operations.</span>
          </h2>

          <div data-reveal className="gf-card gf-load-card mt-12 max-w-xl p-8 sm:p-9">
            <div className="mb-8 flex items-center gap-5">
              <Zap className="gf-load-zap" size={46} strokeWidth={1.7} />
              <p className="text-[25px] font-semibold leading-none" style={{ color: "var(--gf-green)" }}>
                Key controllable loads
              </p>
            </div>
            <div className="grid grid-cols-2 gap-x-10 gap-y-9">
              {LOADS.map((load) => (
                <div key={load.label} className="gf-load-item">
                  <span className="gf-load-icon">{load.icon}</span>
                  <span className="text-[19px] font-semibold leading-tight" style={{ color: "var(--gf-ink)" }}>
                    {load.label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div data-reveal className="gf-load-charts relative hidden min-h-[560px] lg:block">
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
            className="absolute left-[1%] top-[44%] z-[2] w-[74%]"
            popupClass="left-[18%] top-[8%]"
          />
        </div>
      </div>
    </div>
  );
}
