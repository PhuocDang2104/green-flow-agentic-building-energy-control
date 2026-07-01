"use client";

import { useEffect, useState } from "react";

export type TargetStatus = "none" | "pending" | "found" | "missing";
export interface TargetState {
  rect: DOMRect | null;
  status: TargetStatus;
}

/**
 * Resolve a `[data-tour-id]` target for the active step: poll until it mounts
 * (≈1.7s → "missing" so the panel can fall back to a centered card), scroll it
 * into view, then keep its rect in sync on scroll/resize. Only re-renders when
 * the measured rect actually changes.
 */
export function useTutorialTarget(targetId: string | undefined, stepKey: string): TargetState {
  const [state, setState] = useState<TargetState>({
    rect: null,
    status: targetId ? "pending" : "none",
  });

  useEffect(() => {
    if (!targetId) {
      setState({ rect: null, status: "none" });
      return;
    }
    setState({ rect: null, status: "pending" });

    let cancelled = false;
    let el: HTMLElement | null = null;
    let last = "";
    const settleTimers: ReturnType<typeof setTimeout>[] = [];
    const selector = `[data-tour-id="${targetId}"]`;

    const measure = () => {
      if (!el || cancelled) return;
      const r = el.getBoundingClientRect();
      const key = `${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.width)},${Math.round(r.height)}`;
      if (key === last) return;
      last = key;
      setState({ rect: r, status: "found" });
    };

    let tries = 0;
    const find = () => {
      if (cancelled) return;
      el = document.querySelector<HTMLElement>(selector);
      if (el) {
        try {
          el.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
        } catch {
          /* older browsers */
        }
        // measure a few times while the smooth-scroll + layout settle
        [80, 260, 520].forEach((ms) => settleTimers.push(setTimeout(measure, ms)));
        return;
      }
      tries += 1;
      if (tries > 40) {
        setState({ rect: null, status: "missing" });
        return;
      }
      settleTimers.push(setTimeout(find, 120));
    };
    find();

    const onChange = () => measure();
    window.addEventListener("resize", onChange);
    window.addEventListener("scroll", onChange, true);
    return () => {
      cancelled = true;
      settleTimers.forEach(clearTimeout);
      window.removeEventListener("resize", onChange);
      window.removeEventListener("scroll", onChange, true);
    };
  }, [targetId, stepKey]);

  return state;
}
