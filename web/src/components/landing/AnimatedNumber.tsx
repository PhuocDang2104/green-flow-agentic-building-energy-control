"use client";

import { useEffect, useRef, useState } from "react";

/** Counts from 0 to `value` whenever `active` becomes true. */
export default function AnimatedNumber({
  value, active, duration = 1.4, suffix = "",
}: {
  value: number; active: boolean; duration?: number; suffix?: string;
}) {
  const [display, setDisplay] = useState(0);
  const raf = useRef(0);

  useEffect(() => {
    if (!active) {
      setDisplay(0);
      return;
    }
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setDisplay(value);
      return;
    }
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / (duration * 1000));
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(Math.round(value * eased));
      if (t < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [active, value, duration]);

  return <>{display}{suffix}</>;
}
