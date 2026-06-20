"use client";

import { Building2, Globe2, Zap } from "lucide-react";
import MetricCard from "./MetricCard";

export default function SectionGlobalEnergy() {
  return (
    <div className="gf-section" data-section="1">
      <div className="grid w-full max-w-6xl items-center gap-10 lg:grid-cols-[1fr_0.8fr]">
        <div>
          <h2 data-reveal className="text-[clamp(26px,4vw,46px)] font-semibold leading-[1.1] tracking-tight"
              style={{ color: "var(--gf-ink)" }}>
            Commercial buildings are<br />
            a <span className="gf-em">global-scale</span> energy challenge
          </h2>
          <div className="mt-7 flex max-w-md flex-col gap-3">
            <div data-reveal>
              <MetricCard icon={<Building2 size={18} />} value="30%">
                Commercial and non-residential buildings account for around 30% of
                global building final energy demand.
              </MetricCard>
            </div>
            <div data-reveal>
              <MetricCard icon={<Zap size={18} />} value="38.6 EJ" accent="cyan">
                Energy used by commercial and non-residential buildings globally in 2019.
              </MetricCard>
            </div>
            <div data-reveal>
              <MetricCard icon={<Globe2 size={18} />} value="~10,700 TWh" accent="cyan">
                That is enough energy to power Singapore for about 185 years.
              </MetricCard>
            </div>
          </div>
        </div>
        {/* right column intentionally empty — the shared Earth sits here */}
        <div className="hidden lg:block" aria-hidden />
      </div>
    </div>
  );
}
