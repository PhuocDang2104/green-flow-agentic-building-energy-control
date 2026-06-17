"use client";

import { Layers } from "lucide-react";
import { LAYER_COLORS, LAYER_LABELS } from "@/lib/constants";
import { useAppStore } from "@/stores/appStore";

export default function LayerPanel() {
  const layers = useAppStore((s) => s.layers);
  const setLayer = useAppStore((s) => s.setLayer);

  return (
    <div className="absolute left-3 top-3 w-48 rounded-2xl border border-border bg-white/95 p-3 shadow-card backdrop-blur">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-text-secondary">
        <Layers size={13} /> Layers
      </div>
      <div className="space-y-1">
        {Object.keys(layers).map((layer) => (
          <label key={layer}
                 className="flex cursor-pointer items-center gap-2 rounded-lg px-1.5 py-1 text-[13px] hover:bg-surface-muted">
            <input
              type="checkbox"
              checked={layers[layer]}
              onChange={(e) => setLayer(layer, e.target.checked)}
              className="h-3.5 w-3.5 accent-teal"
            />
            <span className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: LAYER_COLORS[layer] || "#cbd5e1" }} />
            {LAYER_LABELS[layer] || layer}
          </label>
        ))}
      </div>
    </div>
  );
}
