"use client";

import { CSSProperties, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { motion } from "motion/react";

const DIM_COLOR = "#030c12";
const DIM_OPACITY = 0.52;
const PAD = 14;

const RING = "0 0 0 1.5px rgba(255,255,255,0.4), 0 0 0 3px rgba(16,185,129,0.92), 0 0 26px 6px rgba(16,185,129,0.32)";
const RING_HI = "0 0 0 1.5px rgba(255,255,255,0.55), 0 0 0 3px rgba(16,185,129,1), 0 0 40px 12px rgba(16,185,129,0.55)";

type Hole = { left: number; top: number; width: number; height: number };

/**
 * Soft spotlight: dims the app for focus and rings the active target(s) but keeps
 * the whole page clickable (hands-on). Supports MULTIPLE bright boxes — the first
 * rect is the primary (pulses), the rest are secondary boxes. A single hole uses
 * a box-shadow (smooth morph); multiple holes use an SVG mask. Read-only steps
 * drop a transparent blocker over the primary; a centered step dims + blocks all.
 */
export default function TutorialOverlay({
  rects,
  interactive,
  pulse,
  reduceMotion,
}: {
  rects: DOMRect[];
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

  const holes: Hole[] = mergeHoles(rects.map((r) => ({
    left: r.left - PAD, top: r.top - PAD, width: r.width + PAD * 2, height: r.height + PAD * 2,
  })));

  const content = (
    <div className="pointer-events-none fixed inset-0 z-[9998]" aria-hidden="true">
      {holes.length === 0 ? (
        <div className="pointer-events-auto fixed inset-0" style={{ background: `rgba(3,12,18,${DIM_OPACITY})` }} />
      ) : holes.length === 1 ? (
        // single hole → box-shadow dim (buttery morph)
        <div
          className="fixed"
          style={{ ...holes[0], borderRadius: 16, boxShadow: `0 0 0 9999px rgba(3,12,18,${DIM_OPACITY})`, ...morph }}
        />
      ) : (
        // multiple holes → SVG mask
        <svg className="fixed inset-0" width="100%" height="100%">
          <defs>
            <mask id="gf-tut-holes">
              <rect x="0" y="0" width="100%" height="100%" fill="white" />
              {holes.map((h, i) => (
                <rect key={i} x={h.left} y={h.top} width={h.width} height={h.height} rx={16} ry={16} fill="black" />
              ))}
            </mask>
          </defs>
          <rect x="0" y="0" width="100%" height="100%" fill={DIM_COLOR} fillOpacity={DIM_OPACITY} mask="url(#gf-tut-holes)" />
        </svg>
      )}

      {/* rings */}
      {holes.map((h, i) => (
        <motion.div
          key={i}
          className="fixed"
          style={{ ...h, borderRadius: 16, ...morph }}
          animate={{ boxShadow: i === 0 && pulse && !reduceMotion ? [RING, RING_HI, RING] : RING }}
          transition={i === 0 && pulse && !reduceMotion
            ? { duration: 1.7, repeat: Infinity, ease: "easeInOut" }
            : { duration: 0.3 }}
        />
      ))}

      {/* read-only steps: block clicks on the primary target only */}
      {!interactive && holes[0] && <div className="pointer-events-auto fixed" style={holes[0]} />}
    </div>
  );

  return createPortal(content, document.body);
}

function mergeHoles(holes: Hole[]): Hole[] {
  const merged: Hole[] = [];
  for (const hole of holes) {
    let current = hole;
    for (let i = 0; i < merged.length; i++) {
      if (!touchesOrOverlaps(current, merged[i])) continue;
      current = unionHole(current, merged[i]);
      merged.splice(i, 1);
      i = -1;
    }
    merged.push(current);
  }
  return merged;
}

function touchesOrOverlaps(a: Hole, b: Hole) {
  const gap = 8;
  return (
    a.left <= b.left + b.width + gap &&
    a.left + a.width + gap >= b.left &&
    a.top <= b.top + b.height + gap &&
    a.top + a.height + gap >= b.top
  );
}

function unionHole(a: Hole, b: Hole): Hole {
  const left = Math.min(a.left, b.left);
  const top = Math.min(a.top, b.top);
  const right = Math.max(a.left + a.width, b.left + b.width);
  const bottom = Math.max(a.top + a.height, b.top + b.height);
  return { left, top, width: right - left, height: bottom - top };
}
