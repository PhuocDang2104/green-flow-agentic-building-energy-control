"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Native long-scroll deck driven by the window scroll. The page scrolls
 * normally (real scrollbar; CSS scroll-snap gives the slide-to-slide feel);
 * this hook reports a CONTINUOUS scroll progress in "section units" (0 = hero,
 * 1 = section 2 top, …) so pinned elements (the Earth, the pie) can be
 * scrubbed/scaled smoothly. No scroll hijacking, no input lock.
 */
export function useScrollDeck(count: number) {
  const [progress, setProgress] = useState(0);
  const [active, setActive] = useState(0);
  const rafRef = useRef(0);

  useEffect(() => {
    const update = () => {
      rafRef.current = 0;
      const vh = window.innerHeight || 1;
      const top = window.scrollY || document.documentElement.scrollTop || 0;
      const p = Math.max(0, Math.min(count - 1, top / vh));
      setProgress(p);
      setActive(Math.round(p));
    };
    const onScroll = () => {
      if (!rafRef.current) rafRef.current = requestAnimationFrame(update);
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    update();
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [count]);

  const goTo = (i: number) => {
    window.scrollTo({ top: Math.round(i) * (window.innerHeight || 0), behavior: "smooth" });
  };

  return { progress, active, goTo };
}
