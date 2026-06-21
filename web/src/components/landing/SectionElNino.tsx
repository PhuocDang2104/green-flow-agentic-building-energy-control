"use client";

import { Snowflake, ThermometerSun, Wind } from "lucide-react";
import MetricCard from "./MetricCard";

export default function SectionElNino() {
  return (
    <div className="gf-section" data-section="4">
      <div className="gf-heat-glow" aria-hidden />
      <div className="grid w-full max-w-6xl items-center gap-10 lg:grid-cols-[1fr_0.92fr]">
        <div>
          <h2
            data-reveal
            className="max-w-md text-[30px] font-semibold leading-[1.14] sm:text-[35px] lg:text-[40px]"
            style={{ color: "var(--gf-ink)" }}
          >
            {`El Ni\u00f1o makes urban heat more `}
            <span className="gf-em">intense and unstable.</span>
          </h2>
          <div className="mt-6 flex max-w-md flex-col gap-3">
            <div data-reveal>
              <MetricCard icon={<ThermometerSun size={18} />} value={"41.3\u00b0C"} accent="warm">
                recorded in Hanoi during the May 2023 heatwave
              </MetricCard>
            </div>
            <div data-reveal>
              <MetricCard icon={<Wind size={18} />} value={"24-27\u00b0C"}>
                typical indoor comfort range maintained by air conditioning in
                Vietnamese office buildings
              </MetricCard>
            </div>
            <div data-reveal>
              <MetricCard icon={<Snowflake size={18} />} value={"14-17\u00b0C"} accent="cyan">
                this sudden cooling is proven to trigger thermal discomfort,
                fatigue and headaches
              </MetricCard>
            </div>
          </div>
        </div>
        <div data-reveal className="gf-article-wrap relative hidden lg:block" data-parallax="0.6">
          <img
            src="/assets/landing/Greenflow Elnino Article.png"
            alt="El Nino heat-risk article: rising urban heat across the globe"
            draggable={false}
            className="relative z-[1] w-full max-w-md select-none rounded-xl"
            style={{
              objectFit: "contain",
              filter: "drop-shadow(0 20px 28px rgba(94,45,22,0.15))",
              transform: "rotateZ(-1.5deg)",
            }}
          />
        </div>
      </div>
    </div>
  );
}
