"use client";

import { createPortal } from "react-dom";
import { CHAPTERS, type TutorialStep } from "./types";

/**
 * Slim 4-chapter progress rail pinned bottom-centre (Observe → Understand →
 * Optimize → Validate). Each segment fills as its steps are visited.
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
    return { ...c, first, fill, active: index >= first && index <= last };
  });

  return createPortal(
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[9999] flex justify-center px-3">
      <div className="flex items-center gap-2 rounded-full border bg-white/95 px-3 py-2 shadow-floating backdrop-blur"
           style={{ borderColor: "rgba(10,125,95,0.16)" }}>
        {chapters.map((c) => (
          <div key={c.id} className="flex items-center gap-1.5">
            <div className="w-[68px] sm:w-[92px]">
              <div className="flex items-center justify-between">
                <span
                  className="text-[10.5px] font-semibold tracking-tight transition-colors"
                  style={{ color: c.active ? c.accent : "#94A3B8" }}
                >
                  {c.label}
                </span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-muted">
                <div
                  className="h-full rounded-full transition-[width] duration-500"
                  style={{ width: `${Math.round(c.fill * 100)}%`, background: c.accent }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>,
    document.body,
  );
}
