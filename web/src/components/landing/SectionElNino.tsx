"use client";

import { Snowflake, ThermometerSun, Wind } from "lucide-react";
import MetricCard from "./MetricCard";

export default function SectionElNino() {
  return (
    <div className="gf-section" data-section="4">
      <div className="gf-heat-glow" data-heatglow />
      <div className="grid w-full max-w-6xl items-center gap-10 lg:grid-cols-[1fr_0.92fr]">
        <div>
          <h2 data-reveal className="max-w-md text-[clamp(24px,3.6vw,42px)] font-semibold leading-[1.12] tracking-tight"
              style={{ color: "var(--gf-ink)" }}>
            El Niño makes urban heat more{" "}
            <span className="gf-em">intense and unstable.</span>
          </h2>
          <div className="mt-6 flex max-w-md flex-col gap-3">
            <div data-reveal>
              <MetricCard icon={<ThermometerSun size={18} />} value="41.3°C" accent="warm">
                recorded in Hanoi during the May 2023 heatwave
              </MetricCard>
            </div>
            <div data-reveal>
              <MetricCard icon={<Wind size={18} />} value="24–27°C">
                typical indoor comfort range maintained by air conditioning in
                Vietnamese office buildings
              </MetricCard>
            </div>
            <div data-reveal>
              <MetricCard icon={<Snowflake size={18} />} value="14–17°C" accent="cyan">
                this sudden cooling is proven to trigger thermal discomfort,
                fatigue and headaches
              </MetricCard>
            </div>
          </div>
        </div>
        <div data-reveal className="relative hidden lg:block" data-parallax="0.6">
          <img
            src="/assets/landing/Greenflow Elnino Article.png"
            alt="El Niño heat-risk article: rising urban heat across the globe"
            draggable={false}
            className="w-full max-w-md select-none rounded-2xl"
            style={{
              objectFit: "contain",
              filter: "drop-shadow(0 30px 50px rgba(120,40,20,0.28))",
              transform: "rotateZ(-2deg)",
            }}
          />
        </div>
      </div>
    </div>
  );
}
