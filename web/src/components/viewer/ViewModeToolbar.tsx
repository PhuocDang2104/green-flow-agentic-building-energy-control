"use client";

import { RotateCcw } from "lucide-react";

/**
 * Camera reset (top-right). The Default/Energy/Comfort/Faults mode bar
 * now lives inside the LayerPanel's Spatial / Zone Analytics group, so the
 * analysis modes are clearly scoped to zones (not the technical layers).
 */
export default function ViewModeToolbar({ onResetCamera }: { onResetCamera: () => void }) {
  return (
    <div className="absolute right-3 top-3 flex items-center gap-1 rounded-full border border-border bg-white/95 p-1 shadow-card backdrop-blur">
      <button onClick={onResetCamera} title="Reset camera"
        className="grid h-7 w-7 place-items-center rounded-full text-text-secondary hover:bg-surface-muted">
        <RotateCcw size={13} />
      </button>
    </div>
  );
}
