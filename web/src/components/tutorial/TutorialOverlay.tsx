"use client";

import { CSSProperties, useEffect, useState } from "react";
import { createPortal } from "react-dom";

const DIM = "rgba(3, 12, 18, 0.56)";
const PAD = 14;

/**
 * Dim the app and cut a soft, green-glowing spotlight around the active target.
 * Visual dim + ring is one smooth-morphing box (box-shadow spread); a set of
 * transparent frame rects around the hole capture clicks so the background is
 * inert — unless `interactive`, in which case the hole stays clickable.
 */
export default function TutorialOverlay({
  rect,
  interactive,
  reduceMotion,
}: {
  rect: DOMRect | null;
  interactive: boolean;
  reduceMotion: boolean;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  const morph: CSSProperties = reduceMotion
    ? {}
    : { transition: "left 320ms cubic-bezier(0.22,1,0.36,1), top 320ms cubic-bezier(0.22,1,0.36,1), width 320ms cubic-bezier(0.22,1,0.36,1), height 320ms cubic-bezier(0.22,1,0.36,1)" };

  const content = (
    <div className="fixed inset-0 z-[9998]" aria-hidden="true">
      {rect ? (
        <>
          {/* visual dim + spotlight ring (pointer-transparent) */}
          <div
            className="pointer-events-none fixed"
            style={{
              left: rect.left - PAD,
              top: rect.top - PAD,
              width: rect.width + PAD * 2,
              height: rect.height + PAD * 2,
              borderRadius: 16,
              boxShadow: `0 0 0 9999px ${DIM}, 0 0 0 1.5px rgba(255,255,255,0.35), 0 0 0 3px rgba(16,185,129,0.9), 0 0 30px 8px rgba(16,185,129,0.35)`,
              ...morph,
            }}
          />
          {/* click-blocking frame around the hole */}
          {frameRects(rect).map((r, i) => (
            <div key={i} className="pointer-events-auto fixed" style={r} />
          ))}
          {/* also block the target itself unless the step allows interaction */}
          {!interactive && (
            <div
              className="pointer-events-auto fixed"
              style={{
                left: rect.left - PAD,
                top: rect.top - PAD,
                width: rect.width + PAD * 2,
                height: rect.height + PAD * 2,
              }}
            />
          )}
        </>
      ) : (
        <div className="pointer-events-auto fixed inset-0" style={{ background: DIM }} />
      )}
    </div>
  );

  return createPortal(content, document.body);
}

function frameRects(rect: DOMRect): CSSProperties[] {
  const left = rect.left - PAD;
  const top = rect.top - PAD;
  const right = rect.right + PAD;
  const bottom = rect.bottom + PAD;
  const W = typeof window !== "undefined" ? window.innerWidth : 0;
  const H = typeof window !== "undefined" ? window.innerHeight : 0;
  const clamp = (v: number) => Math.max(0, v);
  return [
    { left: 0, top: 0, width: W, height: clamp(top) },
    { left: 0, top: bottom, width: W, height: clamp(H - bottom) },
    { left: 0, top: clamp(top), width: clamp(left), height: clamp(bottom - top) },
    { left: right, top: clamp(top), width: clamp(W - right), height: clamp(bottom - top) },
  ];
}
