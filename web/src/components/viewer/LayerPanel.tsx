"use client";

import { Layers } from "lucide-react";
import { LAYER_LABELS, PLANNED_LAYERS } from "@/lib/constants";
import { useAppStore } from "@/stores/appStore";

export default function LayerPanel() {
  const layers = useAppStore((s) => s.layers);
  const setLayer = useAppStore((s) => s.setLayer);

  return (
    <div className="absolute left-3 top-3 w-44 rounded-2xl border border-border bg-white/95 p-3 shadow-card backdrop-blur">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-text-secondary">
        <Layers size={13} /> Layers
      </div>
      <div className="space-y-1.5">
        {Object.keys(layers).map((layer) => (
          <label key={layer} className="flex cursor-pointer items-center gap-2 text-[13px]">
            <input
              type="checkbox"
              checked={layers[layer]}
              onChange={(e) => setLayer(layer, e.target.checked)}
              className="h-3.5 w-3.5 accent-teal"
            />
            {LAYER_LABELS[layer] || layer}
          </label>
        ))}
        {PLANNED_LAYERS.map((layer) => (
          <label key={layer} className="flex items-center gap-2 text-[13px] text-text-muted">
            <input type="checkbox" disabled className="h-3.5 w-3.5" />
            {LAYER_LABELS[layer]}
            <span className="text-[10px]">(IFC P1)</span>
          </label>
        ))}
      </div>
    </div>
  );
}
