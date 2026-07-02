"use client";

import { useAppStore } from "@/stores/appStore";

const LEGENDS: Record<string, { label: string; stops: { color: string; text: string }[] }> = {
  energy: {
    label: "Zone load",
    stops: [
      { color: "#17A34A", text: "low" },
      { color: "#F59E0B", text: "mid" },
      { color: "#DC2626", text: "high" },
    ],
  },
  comfort: {
    label: "Comfort risk",
    stops: [
      { color: "#17A34A", text: "normal" },
      { color: "#F59E0B", text: "watch" },
      { color: "#DC2626", text: "high" },
    ],
  },
  faults: {
    label: "Open faults",
    stops: [
      { color: "#DC2626", text: "critical" },
      { color: "#F59E0B", text: "warning" },
      { color: "#94A3B8", text: "none" },
    ],
  },
};

export default function MetricLegend() {
  const activeMetric = useAppStore((s) => s.activeMetric);
  const legend = LEGENDS[activeMetric];
  if (!legend) return null;
  return (
    <div className="absolute bottom-3 left-3 flex items-center gap-3 rounded-full border border-border bg-white/95 px-3.5 py-1.5 text-xs shadow-card backdrop-blur">
      <span className="font-medium text-text-secondary">{legend.label}</span>
      {legend.stops.map((s) => (
        <span key={s.text} className="flex items-center gap-1 text-text-muted">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
          {s.text}
        </span>
      ))}
    </div>
  );
}
