"use client";

import { CSSProperties, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { motion } from "motion/react";

const DIM = "rgba(3, 12, 18, 0.52)";
const PAD = 14;

const RING = "0 0 0 1.5px rgba(255,255,255,0.4), 0 0 0 3px rgba(16,185,129,0.92), 0 0 26px 6px rgba(16,185,129,0.32)";
const RING_HI = "0 0 0 1.5px rgba(255,255,255,0.55), 0 0 0 3px rgba(16,185,129,1), 0 0 40px 12px rgba(16,185,129,0.55)";

/**
 * Soft spotlight: dims the app for focus and rings the active target, but keeps
 * the whole page clickable so the spotlighted region (and the rest of the UI)
 * stays fully interactive — the tour is hands-on. Only a read-only step
 * (`interactive={false}`) drops a transparent blocker over the target, and a
 * centered step (no rect) dims + blocks the whole screen like a modal.
 */
export default function TutorialOverlay({
  rect,
  interactive,
  pulse,
  reduceMotion,
}: {
  rect: DOMRect | null;
  interactive: boolean;
  pulse: boolean;
  reduceMotion: boolean;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  const morph: CSSProperties = reduceMotion
    ? {}
    : { transition: "left 320ms cubic-bezier(0.22,1,0.36,1), top 320ms cubic-bezier(0.22,1,0.36,1), width 320ms cubic-bezier(0.22,1,0.36,1), height 320ms cubic-bezier(0.22,1,0.36,1)" };

  const hole: CSSProperties | null = rect
    ? { left: rect.left - PAD, top: rect.top - PAD, width: rect.width + PAD * 2, height: rect.height + PAD * 2 }
    : null;

  // pointer-events-none container → the page underneath stays fully clickable;
  // only opt-in children (target blocker / centered modal) capture clicks.
  const content = (
    <div className="pointer-events-none fixed inset-0 z-[9998]" aria-hidden="true">
      {rect && hole ? (
        <>
          {/* visual dim (box-shadow spread; captures no clicks) */}
          <div
            className="fixed"
            style={{ ...hole, borderRadius: 16, boxShadow: `0 0 0 9999px ${DIM}`, ...morph }}
          />
          {/* spotlight ring — pulses on hands-on steps */}
          <motion.div
            className="fixed"
            style={{ ...hole, borderRadius: 16, ...morph }}
            animate={{ boxShadow: pulse && !reduceMotion ? [RING, RING_HI, RING] : RING }}
            transition={pulse && !reduceMotion
              ? { duration: 1.7, repeat: Infinity, ease: "easeInOut" }
              : { duration: 0.3 }}
          />
          {/* read-only steps: block clicks on the target only (rest stays usable) */}
          {!interactive && <div className="pointer-events-auto fixed" style={hole} />}
        </>
      ) : (
        <div className="pointer-events-auto fixed inset-0" style={{ background: DIM }} />
      )}
    </div>
  );

  return createPortal(content, document.body);
}
