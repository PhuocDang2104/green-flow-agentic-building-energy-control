"use client";

import { ArrowRight, Leaf } from "lucide-react";
import MagneticButton from "./MagneticButton";

export default function SectionFinalCTA() {
  return (
    <div className="gf-section" data-section="6">
      <div className="grid w-full max-w-6xl items-center gap-10 lg:grid-cols-[1fr_0.9fr]">
        <div>
          <h2 data-reveal className="text-[clamp(28px,4.6vw,54px)] font-semibold leading-[1.06] tracking-tight"
              style={{ color: "var(--gf-ink)" }}>
            Smarter building operations<br />
            <span className="gf-em">start with</span>{" "}
            <span className="inline-flex items-center gap-2" style={{ color: "var(--gf-green)" }}>
              <Leaf size={34} className="inline" /> greenflow
            </span>
          </h2>
          <p data-reveal className="mt-5 max-w-md text-[15px]" style={{ color: "var(--gf-muted)" }}>
            An AI-powered building intelligence platform for reducing energy
            waste without compromising comfort.
          </p>
          <div data-reveal className="mt-7">
            <MagneticButton href="/dashboard">
              Enter Demo <ArrowRight size={17} />
            </MagneticButton>
          </div>
        </div>

        <div data-reveal className="relative hidden lg:block" data-parallax="0.5">
          <img
            src="/assets/landing/greenflow_product_element.png"
            alt="GreenFlow smart commercial building with live energy and comfort metrics"
            draggable={false}
            className="w-full max-w-md select-none"
            style={{ objectFit: "contain", filter: "drop-shadow(0 28px 44px rgba(0,60,30,0.2))" }}
          />
        </div>
      </div>
    </div>
  );
}
