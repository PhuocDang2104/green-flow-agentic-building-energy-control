"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type React from "react";
import "@/styles/landing.css";
import { AuroraBackground } from "@/components/ui/aurora-background";
import EarthScene from "./EarthScene";
import GreenflowNav from "./GreenflowNav";
import SectionDots from "./SectionDots";
import SectionHero from "./SectionHero";
import SectionGlobalEnergy from "./SectionGlobalEnergy";
import SectionControllableLoads from "./SectionControllableLoads";
import SectionHanoiBreakdown from "./SectionHanoiBreakdown";
import SectionElNino from "./SectionElNino";
import SectionProblem from "./SectionProblem";
import SectionFinalCTA from "./SectionFinalCTA";
import PinnedPieChart from "./PinnedPieChart";
import { useScrollDeck } from "./useScrollDeck";

const COUNT = 7;
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const smooth = (a: number, b: number, x: number) => {
  const t = clamp01((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};

export default function LandingExperience() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [themeMix, setThemeMix] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);

  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const { progress, active, goTo } = useScrollDeck(COUNT);

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

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const sections = Array.from(root.querySelectorAll<HTMLElement>(".gf-section"));
    sections.forEach((section, index) => {
      const visible = index === active;
      section.classList.toggle("is-visible", visible);
      section.setAttribute("aria-hidden", visible ? "false" : "true");
    });
  }, [active]);

  const earthOpacity = 1 - smooth(1.5, 2.05, progress);
  const auroraOpacity = 0.68 * (1 - smooth(0.2, 1.25, progress));
  const glowStyle = {
    "--gf-a-x": `${50 + Math.sin(progress * 0.9) * 10}%`,
    "--gf-a-y": `${78 - progress * 3}%`,
    "--gf-b-x": `${78 - Math.min(progress, 6) * 5}%`,
    "--gf-b-y": `${30 + Math.sin(progress * 0.7) * 9}%`,
    "--gf-shift-x": `${Math.sin(progress * 1.1) * 18}px`,
    "--gf-shift-y": `${Math.cos(progress * 0.8) * 14}px`,
  } as React.CSSProperties;

  const sections = useMemo(
    () => (
      <>
        <SectionHero />
        <SectionGlobalEnergy />
        <SectionControllableLoads />
        <SectionHanoiBreakdown active={active === 3} />
        <SectionElNino />
        <SectionProblem />
        <SectionFinalCTA />
      </>
    ),
    [active],
  );

  return (
    <div className={`landing-root ${theme === "dark" ? "dark" : ""}`} ref={rootRef}>
      <div className="gf-bg-glow" style={glowStyle} />
      <AuroraBackground
        className="gf-hero-aurora bg-transparent dark:bg-transparent"
        showRadialGradient
        style={{
          opacity: auroraOpacity,
          transform: `translate3d(${progress * -18}px, ${progress * 10}px, 0)`,
        }}
      >
        <span className="sr-only">GreenFlow aurora background</span>
      </AuroraBackground>

      <div className="gf-earth-stage" style={{ opacity: earthOpacity }}>
        <EarthScene progress={progress} themeMix={themeMix} reduced={!!reduced} />
      </div>

      <GreenflowNav
        active={active}
        theme={theme}
        onToggleTheme={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
        onNav={goTo}
      />

      <PinnedPieChart progress={progress} />

      <div
        className="gf-stage"
        style={{ transform: `translate3d(0, -${progress * 100}vh, 0)` }}
      >
        {sections}
      </div>

      <SectionDots count={COUNT} active={active} onNav={goTo} />

      <footer
        className="pointer-events-none fixed bottom-3 left-1/2 z-20 -translate-x-1/2 text-[11px]"
        style={{ color: "var(--gf-muted)" }}
      >
        GreenFlow - Scroll to explore
      </footer>
    </div>
  );
}
