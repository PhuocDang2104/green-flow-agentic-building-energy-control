"use client";

import { CSSProperties, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { motion } from "motion/react";
import { ArrowLeft, ArrowRight, RotateCcw, Sparkles, X } from "lucide-react";
import { CHAPTERS, type TutorialStep } from "./types";

const GAP = 16;
const MARGIN = 12;
const PANEL_W = 400;

export default function TutorialPanel({
  step,
  index,
  total,
  rect,
  reduceMotion,
  onBack,
  onNext,
  onSkip,
  onReplay,
  onFinish,
}: {
  step: TutorialStep;
  index: number;
  total: number;
  rect: DOMRect | null;
  reduceMotion: boolean;
  onBack: () => void;
  onNext: () => void;
  onSkip: () => void;
  onReplay: () => void;
  onFinish: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const nextRef = useRef<HTMLButtonElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  const centered = !rect || step.placement === "center";

  const chapter = CHAPTERS.find((c) => c.id === step.chapter)!;
  const isFirst = index === 0;
  const isLast = index === total - 1;

  // measure the panel and place it beside the target (clamped to the viewport)
  useLayoutEffect(() => {
    if (centered) { setPos(null); return; }
    const el = ref.current;
    if (!el || !rect) return;
    const pw = el.offsetWidth || PANEL_W;
    const ph = el.offsetHeight || 220;
    const W = window.innerWidth;
    const H = window.innerHeight;
    let left: number;
    let top: number;
    switch (step.placement) {
      case "top":
        left = rect.left + rect.width / 2 - pw / 2; top = rect.top - ph - GAP; break;
      case "left":
        left = rect.left - pw - GAP; top = rect.top + rect.height / 2 - ph / 2; break;
      case "right":
        left = rect.right + GAP; top = rect.top + rect.height / 2 - ph / 2; break;
      case "bottom":
      default:
        left = rect.left + rect.width / 2 - pw / 2; top = rect.bottom + GAP; break;
    }
    left = Math.min(Math.max(MARGIN, left), W - pw - MARGIN);
    top = Math.min(Math.max(MARGIN, top), H - ph - MARGIN);
    setPos({ left, top });
  }, [rect, step.placement, step.id, centered]);

  // focus the primary action when the step changes
  useLayoutEffect(() => { nextRef.current?.focus(); }, [step.id]);

  const style: CSSProperties = centered
    ? { left: "50%", top: "50%", transform: "translate(-50%, -50%)", width: PANEL_W }
    : { left: pos?.left ?? -9999, top: pos?.top ?? -9999, width: PANEL_W };

  return createPortal(
    <motion.div
      ref={ref}
      data-gf-tutorial-panel
      role="dialog"
      aria-modal="true"
      aria-labelledby="gf-tut-title"
      aria-describedby="gf-tut-body"
      initial={reduceMotion ? false : { opacity: 0, y: 8, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
      className="pointer-events-auto fixed z-[9999] max-w-[calc(100vw-24px)] overflow-hidden rounded-card border bg-white shadow-floating"
      style={{ ...style, borderColor: "rgba(10,125,95,0.16)" }}
    >
      {/* accent header strip */}
      <div className="h-1 w-full" style={{ background: chapter.accent }} />

      <div className="p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <span
            className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold"
            style={{ background: `${chapter.accent}14`, color: chapter.accent }}
          >
            <Sparkles size={11} /> {chapter.label}
          </span>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium tabular-nums text-text-muted">
              {index + 1} / {total}
            </span>
            <button
              onClick={onSkip}
              aria-label="Exit tutorial"
              className="grid h-6 w-6 place-items-center rounded-full text-text-muted transition hover:bg-surface-muted hover:text-text-primary"
            >
              <X size={14} />
            </button>
          </div>
        </div>

        <h3 id="gf-tut-title" className="text-[16px] font-semibold leading-tight tracking-tight text-text-primary">
          {step.title}
        </h3>
        <p id="gf-tut-body" className="mt-1.5 text-[13px] leading-relaxed text-text-secondary">
          {step.body}
        </p>

        {step.chips && step.chips.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {step.chips.map((chip) => (
              <span
                key={chip}
                className="rounded-lg bg-surface-muted px-2 py-1 text-[11px] font-medium text-text-secondary"
              >
                {chip}
              </span>
            ))}
          </div>
        )}

        <div className="mt-4 flex items-center gap-2">
          <button
            onClick={onBack}
            disabled={isFirst}
            className="flex items-center gap-1 rounded-button border border-border px-2.5 py-1.5 text-[12px] font-medium text-text-secondary transition hover:bg-surface-muted disabled:opacity-40"
          >
            <ArrowLeft size={13} /> Back
          </button>

          <button
            onClick={onSkip}
            className="rounded-button px-2.5 py-1.5 text-[12px] font-medium text-text-muted transition hover:text-text-primary"
          >
            Skip
          </button>

          <div className="ml-auto flex items-center gap-2">
            {isLast && (
              <button
                onClick={onReplay}
                className="flex items-center gap-1 rounded-button border border-border px-2.5 py-1.5 text-[12px] font-medium text-text-secondary transition hover:bg-surface-muted"
              >
                <RotateCcw size={13} /> Replay
              </button>
            )}
            <button
              ref={nextRef}
              onClick={isLast ? onFinish : onNext}
              className="flex items-center gap-1 rounded-button bg-teal px-3.5 py-1.5 text-[12px] font-semibold text-white shadow-sm transition hover:bg-teal/90"
            >
              {isLast ? "Finish" : "Next"} {!isLast && <ArrowRight size={13} />}
            </button>
          </div>
        </div>
      </div>
    </motion.div>,
    document.body,
  );
}
