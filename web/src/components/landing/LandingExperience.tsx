"use client";

import { useEffect, useRef, useState } from "react";
import "@/styles/landing.css";
import EarthScene from "./EarthScene";
import GreenflowNav from "./GreenflowNav";
import SectionDots from "./SectionDots";
import CloudWipe from "./CloudWipe";
import SectionHero from "./SectionHero";
import SectionGlobalEnergy from "./SectionGlobalEnergy";
import SectionControllableLoads from "./SectionControllableLoads";
import SectionHanoiBreakdown from "./SectionHanoiBreakdown";
import SectionElNino from "./SectionElNino";
import SectionProblem from "./SectionProblem";
import SectionFinalCTA from "./SectionFinalCTA";
import { useFullPageNavigation } from "./useFullPageNavigation";
import { useMouseParallax } from "./useMouseParallax";

const COUNT = 7;

export default function LandingExperience() {
  const [active, setActive] = useState(0);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [themeMix, setThemeMix] = useState(0);
  const stageRef = useRef<HTMLDivElement>(null);
  const cloudRef = useRef<HTMLDivElement>(null);
  const parallaxRef = useMouseParallax(true);

  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const { goTo } = useFullPageNavigation({ stageRef, cloudRef, count: COUNT, setActive });

  // animate themeMix toward target so the Earth + background morph smoothly
  useEffect(() => {
    const target = theme === "dark" ? 1 : 0;
    let raf = 0;
    const tick = () => {
      setThemeMix((m) => {
        const next = m + (target - m) * 0.12;
        if (Math.abs(target - next) < 0.01) return target;
        raf = requestAnimationFrame(tick);
        return next;
      });
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [theme]);

  return (
    <div className={`landing-root ${theme === "dark" ? "dark" : ""}`} ref={parallaxRef}>
      <div className="gf-bg-glow" />

      <div
        className="gf-earth-stage"
        data-parallax="0.25"
        style={{ opacity: active <= 1 ? 1 : 0, transition: "opacity 0.9s ease" }}
      >
        <EarthScene section={active} themeMix={themeMix} reduced={!!reduced} />
      </div>

      <GreenflowNav
        active={active}
        theme={theme}
        onToggleTheme={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
        onNav={goTo}
      />

      <div className="gf-stage" ref={stageRef}>
        <SectionHero />
        <SectionGlobalEnergy />
        <SectionControllableLoads active={active === 2} themeMix={themeMix} />
        <SectionHanoiBreakdown active={active === 3} />
        <SectionElNino />
        <SectionProblem />
        <SectionFinalCTA />
      </div>

      <CloudWipe ref={cloudRef} />
      <SectionDots count={COUNT} active={active} onNav={goTo} />

      <footer className="pointer-events-none fixed bottom-3 left-1/2 z-20 -translate-x-1/2 text-[11px]"
              style={{ color: "var(--gf-muted)" }}>
        GreenFlow · Scroll, swipe or use arrow keys
      </footer>
    </div>
  );
}
