"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import "@/styles/landing.css";
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

  // turn on slide-style scroll-snap on the document only while the landing is mounted
  useEffect(() => {
    const html = document.documentElement;
    html.classList.add("gf-snap");
    return () => html.classList.remove("gf-snap");
  }, []);

  // smoothly animate themeMix toward target so the Earth + background morph
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

  // reveal section content as each section scrolls into view
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const sections = Array.from(root.querySelectorAll<HTMLElement>(".gf-section"));
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) e.target.classList.add("is-visible");
        }
      },
      { threshold: 0.4 }, // root = viewport (window scroll)
    );
    sections.forEach((s) => io.observe(s));
    // hero is visible immediately
    sections[0]?.classList.add("is-visible");
    return () => io.disconnect();
  }, []);

  // ----- scroll-driven values for the pinned elements -----
  const earthOpacity = 1 - smooth(1.45, 2.0, progress); // globe fades out into the building
  const cloudOpacity = reduced
    ? 0
    : Math.max(0, 1 - Math.abs(progress - 1.5) / 0.42) * 0.85; // mist flash on 2->3 zoom-in

  // the pie stays pinned and scales up + drifts gently down as you scroll 2 -> 3
  const pieT = clamp01(progress - 2);
  const pieOpacity = smooth(1.62, 1.95, progress) * (1 - smooth(3.02, 3.32, progress));
  const pieWidth = 30 + pieT * 11;   // vw
  const pieLeft = 4 + pieT * 1.5;    // vw
  const pieCenter = 50 + pieT * 5;   // vh — vertically centred, drifts gently down

  // sections don't depend on scroll progress, so memoise them away from re-renders
  const sections = useMemo(
    () => (
      <>
        <SectionHero />
        <SectionGlobalEnergy />
        <SectionControllableLoads active={active === 2} themeMix={themeMix} />
        <SectionHanoiBreakdown active={active === 3} />
        <SectionElNino />
        <SectionProblem />
        <SectionFinalCTA />
      </>
    ),
    [active, themeMix],
  );

  return (
    <div className={`landing-root ${theme === "dark" ? "dark" : ""}`} ref={rootRef}>
      <div className="gf-bg-glow" />

      {/* pinned globe — scrubbed by scroll progress */}
      <div className="gf-earth-stage" style={{ opacity: earthOpacity }}>
        <EarthScene progress={progress} themeMix={themeMix} reduced={!!reduced} />
      </div>

      <GreenflowNav
        active={active}
        theme={theme}
        onToggleTheme={() => setTheme((t) => (t === "light" ? "dark" : "light"))}
        onNav={goTo}
      />

      <div className="gf-stage">{sections}</div>

      {/* pinned pie — scrolls smoothly down + scales between section 2 and 3 */}
      <img
        src="/assets/landing/HVAC_light_pie.png"
        alt="Energy share by end use — HVAC 48%, Lighting 22%"
        aria-hidden={pieOpacity < 0.02}
        draggable={false}
        className="gf-pie-fly"
        style={{
          left: `${pieLeft}vw`,
          top: `${pieCenter}vh`,
          width: `${pieWidth}vw`,
          transform: "translateY(-50%)",
          opacity: pieOpacity,
          visibility: pieOpacity < 0.01 ? "hidden" : "visible",
        }}
      />

      <div className="gf-cloud-wipe" style={{ opacity: cloudOpacity }} aria-hidden />

      <SectionDots count={COUNT} active={active} onNav={goTo} />

      <footer className="pointer-events-none fixed bottom-3 left-1/2 z-20 -translate-x-1/2 text-[11px]"
              style={{ color: "var(--gf-muted)" }}>
        GreenFlow · Scroll to explore
      </footer>
    </div>
  );
}
