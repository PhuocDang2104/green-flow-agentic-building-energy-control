"use client";

import { fmtTime, titleCase } from "@/lib/format";
import StatusPill from "@/components/shared/StatusPill";
import EmptyState from "@/components/shared/EmptyState";
import type { SimulationRun } from "@/lib/types";

export default function ScenarioComparisonTable({ runs }: { runs: SimulationRun[] }) {
  return (
    <div className="card-elevated overflow-hidden">
      <div className="border-b border-border px-5 py-3">
        <h3 className="text-sm font-semibold">Simulation runs</h3>
      </div>
      {runs.length === 0 ? (
        <EmptyState title="No simulation runs yet" />
      ) : (
        <div className="max-h-80 overflow-y-auto">
          <table className="w-full text-[13px]">
            <thead className="sticky top-0 bg-surface">
              <tr className="text-left text-xs text-text-muted">
                {["Run", "Kind", "Engine", "Energy", "Peak", "Comfort viol.", "Time"].map((h) => (
                  <th key={h} className="px-5 py-2.5 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-t border-border/60">
                  <td className="px-5 py-2.5 font-medium">
                    {titleCase(r.baseline_label || r.run_kind)}
                  </td>
                  <td className="px-5 py-2.5"><StatusPill status={
                    r.run_kind === "baseline" ? "empty" : "normal"} label={r.run_kind} /></td>
                  <td className="px-5 py-2.5 text-text-secondary">{r.engine}</td>
                  <td className="px-5 py-2.5">{r.totals ? `${r.totals.energy_kwh} kWh` : "–"}</td>
                  <td className="px-5 py-2.5">{r.totals ? `${r.totals.peak_demand_kw} kW` : "–"}</td>
                  <td className="px-5 py-2.5">{r.totals ? `${r.totals.comfort_violation_minutes} min` : "–"}</td>
                  <td className="px-5 py-2.5 text-text-muted">{fmtTime(r.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
