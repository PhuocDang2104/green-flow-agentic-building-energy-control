"use client";

import { Cpu, Layers, Boxes } from "lucide-react";
import { LAYER_COLORS, LAYER_LABELS } from "@/lib/constants";
import { useAppStore } from "@/stores/appStore";

// Two independent groups. Controls for analysis (zone mode bar) and per-layer
// heatmaps live in the floating AnalysisBar, not in this card.
function LayerRow({ layer, label, onColor }: { layer: string; label?: string; onColor?: string }) {
  const layers = useAppStore((s) => s.layers);
  const setLayer = useAppStore((s) => s.setLayer);
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-lg px-1.5 py-1 text-[13px] hover:bg-surface-muted">
      <input type="checkbox" checked={layers[layer] ?? false}
        onChange={(e) => setLayer(layer, e.target.checked)} className="h-3.5 w-3.5 accent-teal" />
      <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: onColor || LAYER_COLORS[layer] || "#cbd5e1" }} />
      {label || LAYER_LABELS[layer] || layer}
    </label>
  );
}

export default function LayerPanel() {
  return (
    <div className="absolute left-3 top-3 w-52 rounded-2xl border border-border bg-white/95 p-3 shadow-card backdrop-blur">
      <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-text-secondary">
        <Layers size={13} /> Layers
      </div>

      {/* Group 1 — Technical Systems */}
      <div className="rounded-xl border border-border/70 p-1.5">
        <div className="mb-0.5 flex items-center gap-1.5 px-1 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
          <Cpu size={11} /> Technical Systems
        </div>
        <LayerRow layer="structural" />
        <LayerRow layer="electrical" />
        <LayerRow layer="hvac" />
      </div>

      {/* Group 2 — Spatial / Zone Analytics */}
      <div className="mt-2 rounded-xl border border-border/70 p-1.5">
        <div className="mb-0.5 flex items-center gap-1.5 px-1 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
          <Boxes size={11} /> Spatial / Zone Analytics
        </div>
        <LayerRow layer="architecture" />
        <LayerRow layer="spaces" />
      </div>
    </div>
  );
}
