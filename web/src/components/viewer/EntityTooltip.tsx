"use client";

import type { ObjectMapEntry, ZoneState } from "@/lib/types";
import { fmtKw, fmtTemp } from "@/lib/format";

export default function EntityTooltip({
  entry, state, x, y,
}: { entry?: ObjectMapEntry; state?: ZoneState; x: number; y: number }) {
  if (!entry) return null;
  return (
    <div
      className="pointer-events-none absolute z-20 max-w-[230px] rounded-xl border border-border bg-white/95 px-3 py-2 text-xs shadow-floating backdrop-blur"
      style={{ left: Math.min(x + 14, 600), top: y + 14 }}
    >
      <p className="font-semibold text-text-primary">{entry.name}</p>
      <p className="text-text-muted">{entry.entity_type}</p>
      {state && entry.layer === "spaces" && (
        <p className="mt-1 text-text-secondary">
          {fmtTemp(state.temperature_c)} · {fmtKw(state.total_power_kw)} ·{" "}
          {state.occupancy_count ?? 0} ppl
        </p>
      )}
    </div>
  );
}
