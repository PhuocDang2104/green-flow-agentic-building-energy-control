"use client";

import { createPortal } from "react-dom";
import { Check } from "lucide-react";
import { CHAPTERS, type TutorialStep } from "./types";

/**
 * Vertical 4-chapter progress rail pinned to the bottom-left corner
 * (Observe → Understand → Optimize → Validate). Each chapter shows a node that
 * lights up when reached (✓ once complete) and a fill bar for within-chapter
 * progress.
 */
export default function TutorialProgressRail({
  steps,
  index,
}: {
  steps: TutorialStep[];
  index: number;
}) {
  const chapters = CHAPTERS.map((c) => {
    const idxs = steps.map((s, i) => (s.chapter === c.id ? i : -1)).filter((i) => i >= 0);
    const first = idxs[0] ?? 0;
    const last = idxs[idxs.length - 1] ?? 0;
    const count = Math.max(1, idxs.length);
    const fill = index > last ? 1 : index < first ? 0 : (index - first + 1) / count;
    const done = index > last;
    const active = index >= first && index <= last;
    return { ...c, fill, done, active };
  });

  return createPortal(
    <div className="pointer-events-none fixed bottom-4 left-4 z-[9999] hidden sm:block">
      <div
        className="rounded-2xl border bg-white/95 px-3 py-3 shadow-floating backdrop-blur"
        style={{ borderColor: "rgba(10,125,95,0.16)" }}
      >
        <div className="mb-2.5 flex items-center justify-between gap-8">
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
            Tour
          </span>
          <span className="text-[10.5px] font-semibold tabular-nums text-text-muted">
            {index + 1} / {steps.length}
          </span>
        </div>
        <ol className="flex flex-col gap-2.5">
          {chapters.map((c, i) => (
            <li key={c.id} className="relative flex items-center gap-2.5">
              {/* connector to the next chapter */}
              {i < chapters.length - 1 && (
                <span
                  className="absolute left-[9px] top-5 h-[calc(100%+0.35rem)] w-[2px] rounded-full"
                  style={{ background: c.done ? c.accent : "#E2E8F0" }}
                />
              )}
              <span
                className="z-10 grid h-[19px] w-[19px] shrink-0 place-items-center rounded-full text-white transition-colors duration-300"
                style={{ background: c.done || c.active ? c.accent : "#CBD5E1" }}
              >
                {c.done ? <Check size={11} strokeWidth={3} /> : <span className="h-1.5 w-1.5 rounded-full bg-white" />}
              </span>
              <div className="w-[116px]">
                <span
                  className="text-[11.5px] font-semibold leading-none transition-colors"
                  style={{ color: c.active ? c.accent : c.done ? "#334155" : "#94A3B8" }}
                >
                  {c.label}
                </span>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-muted">
                  <div
                    className="h-full rounded-full transition-[width] duration-500"
                    style={{ width: `${Math.round(c.fill * 100)}%`, background: c.accent }}
                  />
                </div>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>,
    document.body,
  );
}
