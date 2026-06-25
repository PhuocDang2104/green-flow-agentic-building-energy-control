"use client";

import { Flame } from "lucide-react";
import { METRICS } from "@/lib/constants";
import { useAppStore } from "@/stores/appStore";

/**
 * Floating analysis controls (bottom-right of the 3D card), kept OUT of the
 * Layers card. Each control only appears when its layer tickbox is enabled:
 *  - Electrical / HVAC heatmap toggles (Technical Systems) — when that layer is on
 *  - Zone analysis-mode bar (Default/Energy/Comfort/Occupancy/Faults) — when Spaces is on
 */

function HeatmapChip({ layer, label, ramp }: {
  layer: "electrical" | "hvac"; label: string; ramp: string[];
}) {
  const on = useAppStore((s) => s.techHeatmap[layer]);
  const setTech = useAppStore((s) => s.setTechHeatmap);
  return (
    <div className="w-[286px] rounded-xl border border-border bg-white/95 px-2.5 py-1.5 shadow-card backdrop-blur">
      <button onClick={() => setTech(layer, !on)}
        className={`flex w-full items-center gap-1.5 text-[12px] font-medium ${on ? "text-teal" : "text-text-secondary"}`}>
        <Flame size={12} />
        <span className="min-w-0 flex-1 truncate text-left">{label} heatmap</span>
        <span className={`rounded px-1.5 text-[10px] ${on ? "bg-teal text-white" : "bg-surface-muted text-text-muted"}`}>
          {on ? "ON" : "OFF"}
        </span>
      </button>
      {on && (
        <div className="mt-1 grid grid-cols-[auto_1fr_auto] items-center gap-1 text-[9px] text-text-muted">
          <span>Low</span>
          <span className="h-1.5 rounded" style={{ background: `linear-gradient(90deg, ${ramp.join(",")})` }} />
          <span>High</span>
        </div>
      )}
    </div>
  );
}

export default function AnalysisBar() {
  const layers = useAppStore((s) => s.layers);
  const activeMetric = useAppStore((s) => s.activeMetric);
  const setMetric = useAppStore((s) => s.setMetric);

  return (
    <div className="pointer-events-none absolute bottom-3 right-3 flex max-w-[calc(100%-1.5rem)] flex-col items-end gap-2">
      {layers.electrical && (
        <div className="pointer-events-auto">
          <HeatmapChip layer="electrical" label="Electrical % Load" ramp={["#22c55e", "#eab308", "#ef4444"]} />
        </div>
      )}
      {layers.hvac && (
        <div className="pointer-events-auto">
          <HeatmapChip layer="hvac" label="HVAC Power" ramp={["#bae6fd", "#38bdf8", "#1d4ed8"]} />
        </div>
      )}
      {layers.spaces && (
        <div className="pointer-events-auto rounded-full border border-border bg-white/95 p-1 shadow-card backdrop-blur">
          <span className="px-2 text-[10px] font-medium text-text-muted">Zones:</span>
          {METRICS.map((m) => (
            <button key={m.id} onClick={() => setMetric(m.id)}
              className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition ${
                activeMetric === m.id ? "bg-teal text-white" : "text-text-secondary hover:bg-surface-muted"}`}>
              {m.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
