"use client";

import { Cpu, Layers, Boxes, Flame } from "lucide-react";
import { LAYER_COLORS, LAYER_LABELS, METRICS } from "@/lib/constants";
import { useAppStore } from "@/stores/appStore";

// Two independent groups (see the digital-twin layer spec):
//  1. Technical Systems  — per-layer tickbox + layer-specific heatmap
//  2. Spatial / Zone     — tickbox + a shared analysis mode bar (the only place
//     Default/Energy/Comfort/Occupancy/Faults applies)
const TECH_LAYERS = ["structural", "fenestration", "electrical", "hvac"];
const SPATIAL_LAYERS = ["architecture", "spaces"];

function LayerRow({ layer }: { layer: string }) {
  const layers = useAppStore((s) => s.layers);
  const setLayer = useAppStore((s) => s.setLayer);
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-lg px-1.5 py-1 text-[13px] hover:bg-surface-muted">
      <input type="checkbox" checked={layers[layer] ?? false}
        onChange={(e) => setLayer(layer, e.target.checked)} className="h-3.5 w-3.5 accent-teal" />
      <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: LAYER_COLORS[layer] || "#cbd5e1" }} />
      {LAYER_LABELS[layer] || layer}
    </label>
  );
}

/** A layer-specific heatmap toggle + legend (Technical Systems group). */
function HeatmapToggle({ layer, metric, ramp }: {
  layer: "electrical" | "hvac"; metric: string; ramp: string[];
}) {
  const visible = useAppStore((s) => s.layers[layer]);
  const on = useAppStore((s) => s.techHeatmap[layer]);
  const setTech = useAppStore((s) => s.setTechHeatmap);
  if (!visible) return null;
  return (
    <div className="ml-6 mt-0.5 rounded-lg bg-surface-muted/60 px-2 py-1.5">
      <button onClick={() => setTech(layer, !on)}
        className={`flex w-full items-center gap-1.5 text-[11px] font-medium ${on ? "text-teal" : "text-text-secondary"}`}>
        <Flame size={12} /> Heatmap: {metric}
        <span className={`ml-auto rounded px-1.5 text-[10px] ${on ? "bg-teal text-white" : "bg-border text-text-muted"}`}>
          {on ? "ON" : "OFF"}
        </span>
      </button>
      {on && (
        <div className="mt-1 flex items-center gap-1 text-[9px] text-text-muted">
          <span>Low</span>
          <span className="h-1.5 flex-1 rounded" style={{ background: `linear-gradient(90deg, ${ramp.join(",")})` }} />
          <span>High</span>
        </div>
      )}
    </div>
  );
}

export default function LayerPanel() {
  const activeMetric = useAppStore((s) => s.activeMetric);
  const setMetric = useAppStore((s) => s.setMetric);

  return (
    <div className="absolute left-3 top-3 max-h-[calc(100%-1.5rem)] w-56 overflow-y-auto rounded-2xl border border-border bg-white/95 p-3 shadow-card backdrop-blur">
      <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-text-secondary">
        <Layers size={13} /> Layers
      </div>

      {/* Group 1 — Technical Systems (tickbox + per-layer heatmap) */}
      <div className="rounded-xl border border-border/70 p-1.5">
        <div className="mb-0.5 flex items-center gap-1.5 px-1 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
          <Cpu size={11} /> Technical Systems
        </div>
        <LayerRow layer="structural" />
        <LayerRow layer="fenestration" />
        <LayerRow layer="electrical" />
        <HeatmapToggle layer="electrical" metric="% Load" ramp={["#22c55e", "#eab308", "#ef4444"]} />
        <LayerRow layer="hvac" />
        <HeatmapToggle layer="hvac" metric="Power" ramp={["#bae6fd", "#38bdf8", "#1d4ed8"]} />
      </div>

      {/* Group 2 — Spatial / Zone Analytics (tickbox + shared mode bar) */}
      <div className="mt-2 rounded-xl border border-border/70 p-1.5">
        <div className="mb-0.5 flex items-center gap-1.5 px-1 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
          <Boxes size={11} /> Spatial / Zone Analytics
        </div>
        <LayerRow layer="architecture" />
        <LayerRow layer="spaces" />
        <div className="mt-1.5 px-1">
          <p className="mb-1 text-[10px] text-text-muted">Analysis mode (zones)</p>
          <div className="flex flex-wrap gap-1">
            {METRICS.map((m) => (
              <button key={m.id} onClick={() => setMetric(m.id)}
                className={`rounded-md px-2 py-0.5 text-[11px] font-medium transition ${
                  activeMetric === m.id ? "bg-teal text-white" : "bg-surface-muted text-text-secondary hover:bg-border"}`}>
                {m.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
