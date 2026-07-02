"use client";

import { CSSProperties } from "react";
import { createPortal } from "react-dom";
import { motion } from "motion/react";
import type { TutorialMedia, TutorialMediaAnchor } from "./types";

const ANCHOR: Record<TutorialMediaAnchor, CSSProperties> = {
  "top-right": { top: 74, right: 20 },
  "bottom-right": { bottom: 92, right: 20 },
  "top-left": { top: 74, left: 22 },
  "bottom-left": { bottom: 118, left: 22 },
  "top-center": { top: 70, left: "50%", transform: "translateX(-50%)" },
};

const OFFSET: Record<TutorialMediaAnchor, { x: number; y: number }> = {
  "top-right": { x: 24, y: -12 },
  "bottom-right": { x: 24, y: 12 },
  "top-left": { x: -24, y: -12 },
  "bottom-left": { x: -24, y: 12 },
  "top-center": { x: 0, y: -16 },
};

/**
 * Decorative floating illustration layer for a step (BIM/real-building imagery,
 * bot mascots, speech bubbles). Rendered above the dim, below the panel,
 * pointer-events-none. Each item animates in from its anchor and gently bobs.
 */
export default function TutorialMedia({
  media,
  reduceMotion,
}: {
  media: TutorialMedia[];
  reduceMotion: boolean;
}) {
  return createPortal(
    <div className="pointer-events-none fixed inset-0 z-[9999]" aria-hidden="true">
      {media.map((m, i) => {
        const off = OFFSET[m.anchor];
        return (
          <motion.div
            key={`${m.src ?? m.variant ?? "media"}-${i}`}
            className="fixed max-w-[46vw]"
            style={{ ...ANCHOR[m.anchor], width: m.width ?? 340 }}
            initial={reduceMotion ? false : { opacity: 0, x: off.x, y: off.y, scale: 0.96 }}
            animate={{ opacity: 1, x: 0, y: 0, scale: 1 }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1], delay: 0.05 + i * 0.12 }}
          >
            <Bob reduceMotion={reduceMotion} delay={i * 0.4}>
              <MediaItem m={m} />
            </Bob>
          </motion.div>
        );
      })}
    </div>,
    document.body,
  );
}

function Bob({ children, reduceMotion, delay }: { children: React.ReactNode; reduceMotion: boolean; delay: number }) {
  if (reduceMotion) return <>{children}</>;
  return (
    <motion.div
      animate={{ y: [0, -8, 0] }}
      transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut", delay }}
    >
      {children}
    </motion.div>
  );
}

function MediaItem({ m }: { m: TutorialMedia }) {
  if (m.variant === "bubble") {
    return (
      <div className="relative rounded-[26px] border border-border/60 bg-white px-5 py-4 shadow-floating">
        {m.title && <p className="mb-1 text-[15px] font-bold tracking-tight text-text-primary">{m.title}</p>}
        {m.bullets && (
          <ul className="space-y-1.5 text-[15px] font-semibold text-text-primary">
            {m.bullets.map((b) => (
              <li key={b} className="flex items-start gap-2">
                <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-teal" />
                {b}
              </li>
            ))}
          </ul>
        )}
        <span className="absolute -bottom-2 left-10 h-4 w-4 rotate-45 border-b border-r border-border/60 bg-white" />
      </div>
    );
  }

  if (m.variant === "float") {
    // bare transparent PNG (bot mascots) — the sign/text is baked into the art
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={m.src} alt={m.alt ?? ""} className="w-full drop-shadow-[0_24px_40px_rgba(15,23,42,0.28)]" draggable={false} />;
  }

  // "card": rounded image with optional title above and caption below
  return (
    <div className="flex flex-col gap-2.5">
      {m.title && (
        <p className="text-[22px] font-bold leading-tight tracking-tight text-text-primary"
           style={{ textShadow: "0 1px 10px rgba(255,255,255,0.6)" }}>
          {m.title}
        </p>
      )}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {m.src && <img src={m.src} alt={m.alt ?? ""}
           className="w-full rounded-2xl border border-white/70 shadow-floating" draggable={false} />}
      {m.caption && (
        <p className="text-[15px] font-medium leading-relaxed text-text-primary"
           style={{ textShadow: "0 1px 10px rgba(255,255,255,0.7)" }}>
          {m.caption}
        </p>
      )}
    </div>
  );
}
