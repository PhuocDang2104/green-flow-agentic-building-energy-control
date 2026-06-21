"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Native long-scroll deck with a GENTLE, slow auto-glide between sections so the
 * pinned scroll-driven animations are clearly visible. The page is still one
 * real scrollable document (scrollbar works); a wheel/key/swipe gesture eases
 * smoothly to the adjacent section over ~1.15s, and dragging the scrollbar
 * softly completes to the nearest section when it goes idle. `progress` is a
 * continuous value (section units) read from window.scrollY for the scrub.
 */
const DUR = 1150; // ms — slow on purpose, to reveal the animation
const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export function useScrollDeck(count: number) {
  const [progress, setProgress] = useState(0);
  const [active, setActive] = useState(0);
  const reportRaf = useRef(0);
  const animating = useRef(false);
  const idxRef = useRef(0);
  const goToRef = useRef<(i: number) => void>(() => {});

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const vh = () => window.innerHeight || 1;

    const report = () => {
      reportRaf.current = 0;
      const p = Math.max(0, Math.min(count - 1, window.scrollY / vh()));
      setProgress(p);
      setActive(Math.round(p));
    };
    const queueReport = () => {
      if (!reportRaf.current) reportRaf.current = requestAnimationFrame(report);
    };

    idxRef.current = Math.round(window.scrollY / vh());

    let animId = 0;
    const animateTo = (i: number) => {
      i = Math.max(0, Math.min(count - 1, i));
      idxRef.current = i;
      const from = window.scrollY;
      const to = i * vh();
      if (reduced || Math.abs(to - from) < 2) {
        window.scrollTo(0, to);
        return;
      }
      cancelAnimationFrame(animId);
      animating.current = true;
      const start = performance.now();
      const step = (now: number) => {
        const t = Math.min(1, (now - start) / DUR);
        window.scrollTo(0, from + (to - from) * easeInOut(t));
        if (t < 1) animId = requestAnimationFrame(step);
        else animating.current = false;
      };
      animId = requestAnimationFrame(step);
    };
    goToRef.current = animateTo;

    // one slow section-glide per wheel gesture
    let wheelCooldown = 0;
    const onWheel = (e: WheelEvent) => {
      if (reduced || e.ctrlKey) return; // let native scroll / pinch-zoom through
      e.preventDefault();
      if (animating.current) return;
      const now = performance.now();
      if (now < wheelCooldown) return;
      const dir = e.deltaY > 0 ? 1 : e.deltaY < 0 ? -1 : 0;
      if (!dir) return;
      wheelCooldown = now + DUR + 140;
      animateTo(idxRef.current + dir);
    };

    const onKey = (e: KeyboardEvent) => {
      if (["ArrowDown", "PageDown", " ", "Spacebar"].includes(e.key)) {
        e.preventDefault();
        if (!animating.current) animateTo(idxRef.current + 1);
      } else if (["ArrowUp", "PageUp"].includes(e.key)) {
        e.preventDefault();
        if (!animating.current) animateTo(idxRef.current - 1);
      } else if (e.key === "Home") {
        e.preventDefault(); animateTo(0);
      } else if (e.key === "End") {
        e.preventDefault(); animateTo(count - 1);
      }
    };

    let touchY = 0;
    const onTouchStart = (e: TouchEvent) => { touchY = e.touches[0].clientY; };
    const onTouchEnd = (e: TouchEvent) => {
      if (reduced || animating.current) return;
      const dy = touchY - e.changedTouches[0].clientY;
      if (Math.abs(dy) > 45) animateTo(idxRef.current + (dy > 0 ? 1 : -1));
    };

    // scrollbar drag / other native scroll: gently complete to nearest on idle
    let idle = 0;
    const onScroll = () => {
      queueReport();
      if (reduced || animating.current) return;
      clearTimeout(idle);
      idle = window.setTimeout(() => {
        if (animating.current) return;
        const i = Math.round(window.scrollY / vh());
        idxRef.current = i;
        if (Math.abs(window.scrollY - i * vh()) > 4) animateTo(i);
      }, 240);
    };

    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("keydown", onKey);
    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchend", onTouchEnd, { passive: true });
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", queueReport);
    report();

    return () => {
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchend", onTouchEnd);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", queueReport);
      cancelAnimationFrame(animId);
      if (reportRaf.current) cancelAnimationFrame(reportRaf.current);
      clearTimeout(idle);
    };
  }, [count]);

  return { progress, active, goTo: (i: number) => goToRef.current(i) };
}
