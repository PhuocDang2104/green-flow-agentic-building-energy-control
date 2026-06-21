"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Virtual full-page deck navigation. The browser document does not perform the
 * visual scroll; wheel, keyboard and swipe gestures advance one locked section
 * at a time while `progress` is animated for shared objects.
 */
const DURATION = 2000;
const REDUCED_DURATION = 220;
const WHEEL_TOLERANCE = 0.5;

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value));

const easeInOut = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

export function useScrollDeck(count: number) {
  const [progress, setProgress] = useState(0);
  const [active, setActive] = useState(0);
  const progressRef = useRef(0);
  const activeRef = useRef(0);
  const animating = useRef(false);
  const animId = useRef(0);
  const reducedRef = useRef(false);

  const goTo = useCallback(
    (index: number) => {
      const next = clamp(index, 0, count - 1);
      if (next === activeRef.current && !animating.current) return;
      if (animating.current) return;

      const from = progressRef.current;
      const to = next;
      const duration = reducedRef.current ? REDUCED_DURATION : DURATION;

      window.dispatchEvent(
        new CustomEvent("gf-section-change", {
          detail: { from: activeRef.current, to: next },
        }),
      );

      activeRef.current = next;
      setActive(next);
      cancelAnimationFrame(animId.current);

      if (Math.abs(to - from) < 0.001) {
        progressRef.current = to;
        setProgress(to);
        return;
      }

      animating.current = true;
      const start = performance.now();

      const step = (now: number) => {
        const t = clamp((now - start) / duration, 0, 1);
        const value = from + (to - from) * easeInOut(t);
        progressRef.current = value;
        setProgress(value);

        if (t < 1) {
          animId.current = requestAnimationFrame(step);
          return;
        }

        progressRef.current = to;
        setProgress(to);
        animating.current = false;
      };

      animId.current = requestAnimationFrame(step);
    },
    [count],
  );

  useEffect(() => {
    reducedRef.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const html = document.documentElement;
    const body = document.body;
    html.classList.add("gf-snap");
    body.classList.add("gf-snap-body");
    window.scrollTo(0, 0);

    const navigateBy = (direction: 1 | -1) => {
      if (animating.current) return;
      goTo(activeRef.current + direction);
    };

    const onWheel = (event: WheelEvent) => {
      if (event.ctrlKey) return;
      event.preventDefault();
      if (Math.abs(event.deltaY) < WHEEL_TOLERANCE) return;
      navigateBy(event.deltaY > 0 ? 1 : -1);
    };

    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, select, [contenteditable='true']")) return;

      if (["ArrowDown", "PageDown", " ", "Spacebar"].includes(event.key)) {
        event.preventDefault();
        navigateBy(1);
      } else if (["ArrowUp", "PageUp"].includes(event.key)) {
        event.preventDefault();
        navigateBy(-1);
      } else if (event.key === "Home") {
        event.preventDefault();
        goTo(0);
      } else if (event.key === "End") {
        event.preventDefault();
        goTo(count - 1);
      }
    };

    let touchY = 0;
    const onTouchStart = (event: TouchEvent) => {
      touchY = event.touches[0]?.clientY ?? 0;
    };
    const onTouchMove = (event: TouchEvent) => {
      event.preventDefault();
    };
    const onTouchEnd = (event: TouchEvent) => {
      const endY = event.changedTouches[0]?.clientY ?? touchY;
      const dy = touchY - endY;
      if (Math.abs(dy) > 22) navigateBy(dy > 0 ? 1 : -1);
    };

    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("keydown", onKey);
    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchmove", onTouchMove, { passive: false });
    window.addEventListener("touchend", onTouchEnd, { passive: true });

    return () => {
      html.classList.remove("gf-snap");
      body.classList.remove("gf-snap-body");
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("touchend", onTouchEnd);
      cancelAnimationFrame(animId.current);
    };
  }, [count, goTo]);

  return { progress, active, goTo };
}
