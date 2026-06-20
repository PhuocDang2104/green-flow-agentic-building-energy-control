"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";
import { Observer } from "gsap/Observer";

gsap.registerPlugin(Observer);

interface Args {
  stageRef: React.RefObject<HTMLDivElement>;
  cloudRef: React.RefObject<HTMLDivElement>;
  count: number;
  setActive: (i: number) => void;
}

/**
 * One-scroll-one-section navigation. GSAP Observer (wheel/touch/pointer) and
 * keyboard drive a locked timeline between absolutely-stacked sections, with a
 * cloud wipe on the 2 -> 3 transition. Returns goTo for nav/dots.
 */
export function useFullPageNavigation({ stageRef, cloudRef, count, setActive }: Args) {
  const activeRef = useRef(0);
  const animating = useRef(false);
  const goToRef = useRef<(n: number) => void>(() => {});

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const sections = Array.from(
      stage.querySelectorAll<HTMLElement>(".gf-section"),
    );
    if (!sections.length) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dur = reduced ? 0.35 : 1.2;

    // initial state: only section 0 visible
    sections.forEach((s, i) => {
      gsap.set(s, {
        autoAlpha: i === 0 ? 1 : 0,
        y: i === 0 ? 0 : 40,
        scale: 1,
        filter: "blur(0px)",
        pointerEvents: i === 0 ? "auto" : "none",
      });
      if (i === 0) s.classList.add("is-active");
    });
    revealChildren(sections[0], reduced, true);

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function goTo(next: number) {
      if (animating.current) return;
      if (next < 0 || next > count - 1) return;
      const cur = activeRef.current;
      if (next === cur) return;

      animating.current = true;
      const forward = next > cur;
      const curEl = sections[cur];
      const nextEl = sections[next];
      // earth + nav/dots update immediately for a continuous feel
      activeRef.current = next;
      setActive(next);

      const tl = gsap.timeline({
        defaults: { ease: "power3.inOut", duration: dur },
        onComplete: () => {
          curEl.classList.remove("is-active");
          nextEl.classList.add("is-active");
          gsap.set([curEl, nextEl], { clearProps: "zIndex" });
          animating.current = false;
        },
      });

      // ----- "keep the pie" shared-element transition between section 2 and 3 -----
      const pieFlip = !reduced && ((cur === 2 && next === 3) || (cur === 3 && next === 2));
      const outPie = pieFlip ? curEl.querySelector<HTMLElement>("[data-pie]") : null;
      const inPie = pieFlip ? nextEl.querySelector<HTMLElement>("[data-pie]") : null;
      if (pieFlip && outPie && inPie) {
        const r1 = outPie.getBoundingClientRect();
        const r2 = inPie.getBoundingClientRect();
        const dx = r1.left - r2.left;
        const dy = r1.top - r2.top;
        const sx = r2.width ? r1.width / r2.width : 1;

        // incoming section sits on top, visible; its other content waits
        gsap.set(nextEl, { autoAlpha: 1, y: 0, scale: 1, filter: "blur(0px)", pointerEvents: "auto", zIndex: 5 });
        gsap.set(curEl, { zIndex: 4 });
        const nextKids = Array.from(nextEl.querySelectorAll<HTMLElement>("[data-reveal]"));
        gsap.set(nextKids, { autoAlpha: 0, y: 24 });

        // the flying pie starts exactly over the outgoing one, then glides down + grows
        gsap.set(inPie, { transformOrigin: "top left", x: dx, y: dy, scale: sx, autoAlpha: 1 });
        gsap.set(outPie, { autoAlpha: 0 });

        const outKids = Array.from(curEl.querySelectorAll<HTMLElement>("[data-reveal]"));
        tl.to(outKids, { autoAlpha: 0, y: forward ? -20 : 20, duration: dur * 0.5, stagger: 0.04 }, 0);
        tl.to(curEl, { autoAlpha: 0, duration: dur * 0.6, pointerEvents: "none" }, dur * 0.2);
        tl.to(inPie, { x: 0, y: 0, scale: 1, duration: dur, ease: "power3.inOut" }, 0);
        tl.add(() => revealChildren(nextEl, reduced, false), dur * 0.6);
        tl.add(() => {
          gsap.set(outPie, { autoAlpha: 1, clearProps: "transform" });
          gsap.set(inPie, { clearProps: "transform" });
        });
        return tl;
      }

      tl.to(curEl, {
        autoAlpha: 0,
        y: forward ? -40 : 40,
        scale: 0.97,
        filter: "blur(6px)",
        pointerEvents: "none",
      }, 0);

      // cloud wipe on the global->loads transition (index 1 -> 2)
      const cloud = cloudRef.current;
      if (cloud && !reduced && ((cur === 1 && next === 2) || (cur === 2 && next === 1))) {
        tl.to(cloud, { autoAlpha: 1, scale: 1.12, duration: dur * 0.45, ease: "sine.out" }, 0.1);
        tl.to(cloud, { autoAlpha: 0, scale: 1.2, duration: dur * 0.55, ease: "sine.in" }, ">-0.1");
      }

      gsap.set(nextEl, {
        autoAlpha: 0,
        y: forward ? 48 : -48,
        scale: 1,
        filter: "blur(8px)",
        pointerEvents: "auto",
      });
      tl.to(nextEl, { autoAlpha: 1, y: 0, filter: "blur(0px)" }, dur * 0.35);
      tl.add(() => revealChildren(nextEl, reduced, false), dur * 0.45);

      return tl;
    }
    goToRef.current = goTo;

    const observer = Observer.create({
      target: window,
      type: "wheel,touch,pointer",
      tolerance: 12,
      preventDefault: true,
      onUp: () => goTo(activeRef.current + 1),   // wheel down / swipe up
      onDown: () => goTo(activeRef.current - 1),
    });

    const onKey = (e: KeyboardEvent) => {
      if (["ArrowDown", "PageDown", " ", "Spacebar"].includes(e.key)) {
        e.preventDefault(); goTo(activeRef.current + 1);
      } else if (["ArrowUp", "PageUp"].includes(e.key)) {
        e.preventDefault(); goTo(activeRef.current - 1);
      } else if (e.key === "Home") {
        e.preventDefault(); goTo(0);
      } else if (e.key === "End") {
        e.preventDefault(); goTo(count - 1);
      }
    };
    window.addEventListener("keydown", onKey);

    return () => {
      observer.kill();
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [count]);

  return { goTo: (n: number) => goToRef.current(n) };
}

function revealChildren(section: HTMLElement, reduced: boolean, immediate: boolean) {
  const kids = Array.from(section.querySelectorAll<HTMLElement>("[data-reveal]"));
  const lines = Array.from(section.querySelectorAll<HTMLElement>(".gf-line-inner"));
  gsap.killTweensOf([...kids, ...lines]);
  if (immediate || reduced) {
    gsap.set(kids, { autoAlpha: 1, y: 0 });
    gsap.set(lines, { yPercent: 0 });
  } else {
    gsap.fromTo(lines, { yPercent: 110 },
      { yPercent: 0, duration: 0.7, ease: "power3.out", stagger: 0.08 });
    gsap.fromTo(kids, { autoAlpha: 0, y: 24 },
      { autoAlpha: 1, y: 0, duration: 0.6, ease: "power3.out", stagger: 0.12, delay: 0.05 });
  }
  // heat glow on the El Niño section
  const heat = section.querySelector<HTMLElement>("[data-heatglow]");
  if (heat) gsap.fromTo(heat, { opacity: 0 }, { opacity: 1, duration: 1 });
}
