"use client";

import { useRef } from "react";
import { useRouter } from "next/navigation";

/** CTA that gently follows the cursor and springs back. */
export default function MagneticButton({
  href, children,
}: { href: string; children: React.ReactNode }) {
  const ref = useRef<HTMLButtonElement>(null);
  const router = useRouter();

  const onMove = (e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(pointer: coarse)").matches) return;
    const r = el.getBoundingClientRect();
    const x = e.clientX - (r.left + r.width / 2);
    const y = e.clientY - (r.top + r.height / 2);
    el.style.transform = `translate(${x * 0.3}px, ${y * 0.4}px)`;
  };
  const reset = () => {
    if (ref.current) ref.current.style.transform = "translate(0,0)";
  };

  return (
    <button
      ref={ref}
      className="gf-cta transition-transform duration-300 ease-out hover:brightness-110"
      onMouseMove={onMove}
      onMouseLeave={reset}
      onClick={() => router.push(href)}
    >
      {children}
    </button>
  );
}
