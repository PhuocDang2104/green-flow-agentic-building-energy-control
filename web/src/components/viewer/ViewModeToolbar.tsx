"use client";

import { RotateCcw } from "lucide-react";
import { METRICS } from "@/lib/constants";
import { useAppStore } from "@/stores/appStore";

export default function ViewModeToolbar({ onResetCamera }: { onResetCamera: () => void }) {
  const activeMetric = useAppStore((s) => s.activeMetric);
  const setMetric = useAppStore((s) => s.setMetric);

  return (
    <div className="absolute right-3 top-3 flex items-center gap-1 rounded-full border border-border bg-white/95 p-1 shadow-card backdrop-blur">
      {METRICS.map((m) => (
        <button
          key={m.id}
          onClick={() => setMetric(m.id)}
          className={`rounded-full px-3 py-1.5 text-xs font-medium transition
            ${activeMetric === m.id ? "bg-teal text-white" : "text-text-secondary hover:bg-surface-muted"}`}
        >
          {m.label}
        </button>
      ))}
      <button
        onClick={onResetCamera}
        title="Reset camera"
        className="grid h-7 w-7 place-items-center rounded-full text-text-secondary hover:bg-surface-muted"
      >
        <RotateCcw size={13} />
      </button>
    </div>
  );
}
