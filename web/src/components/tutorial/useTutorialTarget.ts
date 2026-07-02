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
export function useTutorialTarget(
  targetId: string | undefined,
  stepKey: string,
  block: ScrollLogicalPosition = "center",
  scrollTargetId?: string,
): TargetState {
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
    const scrollSelector = scrollTargetId ? `[data-tour-id="${scrollTargetId}"]` : selector;

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
          const scrollEl = document.querySelector<HTMLElement>(scrollSelector) ?? el;
          scrollEl.scrollIntoView({ behavior: "smooth", block, inline: "center" });
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
  }, [targetId, stepKey, block, scrollTargetId]);

  return state;
}

/**
 * Resolve a set of secondary `[data-tour-id]` targets (for steps that box more
 * than one element). No scroll; tracks rects on scroll/resize. Returns only the
 * targets currently mounted, in order.
 */
export function useSecondaryRects(ids: string[] | undefined, stepKey: string): DOMRect[] {
  const [rects, setRects] = useState<DOMRect[]>([]);
  const key = (ids ?? []).join("|");

  useEffect(() => {
    if (!ids || !ids.length) { setRects([]); return; }
    let cancelled = false;
    let tries = 0;
    const timers: ReturnType<typeof setTimeout>[] = [];

    const measure = () => {
      if (cancelled) return;
      const rs: DOMRect[] = [];
      for (const id of ids) {
        const el = document.querySelector<HTMLElement>(`[data-tour-id="${id}"]`);
        if (el) rs.push(el.getBoundingClientRect());
      }
      setRects(rs);
    };
    const poll = () => {
      if (cancelled) return;
      measure();
      tries += 1;
      const missing = ids.some((id) => !document.querySelector(`[data-tour-id="${id}"]`));
      if (missing && tries < 40) timers.push(setTimeout(poll, 140));
    };
    poll();

    const onChange = () => measure();
    window.addEventListener("resize", onChange);
    window.addEventListener("scroll", onChange, true);
    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
      window.removeEventListener("resize", onChange);
      window.removeEventListener("scroll", onChange, true);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, stepKey]);

  return rects;
}
