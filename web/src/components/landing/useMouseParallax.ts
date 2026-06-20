"use client";

import { useEffect, useRef } from "react";

/** Subtle pointer parallax. Returns a ref to attach; children with
 *  data-parallax="<depth>" translate/rotate gently. Disabled on touch and
 *  reduced motion. */
export function useMouseParallax(enabled = true) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!enabled) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    if (reduced || coarse) return;
    const el = ref.current;
    if (!el) return;

    let raf = 0;
    let tx = 0;
    let ty = 0;
    const onMove = (e: MouseEvent) => {
      const nx = (e.clientX / window.innerWidth - 0.5) * 2;
      const ny = (e.clientY / window.innerHeight - 0.5) * 2;
      tx = nx;
      ty = ny;
      if (!raf) raf = requestAnimationFrame(apply);
    };
    const apply = () => {
      raf = 0;
      el.querySelectorAll<HTMLElement>("[data-parallax]").forEach((node) => {
        const depth = parseFloat(node.dataset.parallax || "0");
        const max = 16 * depth;
        node.style.transform =
          `translate3d(${(-tx * max).toFixed(2)}px, ${(-ty * max).toFixed(2)}px, 0) ` +
          `rotateX(${(ty * 2 * depth).toFixed(2)}deg) rotateY(${(-tx * 2 * depth).toFixed(2)}deg)`;
      });
    };
    window.addEventListener("mousemove", onMove);
    return () => {
      window.removeEventListener("mousemove", onMove);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [enabled]);

  return ref;
}
