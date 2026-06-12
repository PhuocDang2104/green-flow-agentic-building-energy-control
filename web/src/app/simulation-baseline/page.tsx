"use client";

import { useCallback, useEffect, useState } from "react";
import { FlaskConical, GitCompareArrows, Loader2 } from "lucide-react";
import PageHeader from "@/components/shell/PageHeader";
import KpiCard from "@/components/dashboard/KpiCard";
import BaselineOptimizedChart from "@/components/simulation/BaselineOptimizedChart";
import ScenarioComparisonTable from "@/components/simulation/ScenarioComparisonTable";
import ActionTraceTimeline from "@/components/simulation/ActionTraceTimeline";
import { useAgentRun } from "@/hooks/useAgentRun";
import { api } from "@/lib/api";
import { fmtVnd } from "@/lib/format";
import type { ComparisonKpi, SimulationRun } from "@/lib/types";

export default function SimulationBaselinePage() {
  const { run, running, start } = useAgentRun();
  const [kpi, setKpi] = useState<ComparisonKpi | null>(null);
  const [runs, setRuns] = useState<SimulationRun[]>([]);
  const [actions, setActions] = useState<any[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);

  const load = useCallback(async () => {
    try {
      const comparison = await api.latestComparison();
      const details = typeof comparison.details_json === "string"
        ? JSON.parse(comparison.details_json)
        : comparison.details_json;
      setKpi(details || comparison);
    } catch { /* none yet */ }
    api.simulations().then((rs) => {
      setRuns(rs);
      const optimized = rs.find((r) => r.run_kind !== "baseline" && r.actions_json?.length);
      setActions(optimized?.actions_json || []);
    }).catch(() => null);
    setRefreshKey((k) => k + 1);
  }, []);

  useEffect(() => { load(); }, [load]);

  // refresh after a simulate run completes
  useEffect(() => {
    if (!running && run) load();
  }, [running, run, load]);

  return (
    <div className="pb-4">
      <PageHeader
        title="Control & Simulation"
        subtitle="Counterfactual proof: same weather and occupancy, only agent actions differ."
        actions={
          <>
            <button className="btn-secondary" disabled={running}
                    onClick={() => start(() => api.compareBaseline())}>
              <GitCompareArrows size={15} /> Compare Baseline
            </button>
            <button className="btn-primary" disabled={running}
                    onClick={() => start(() => api.simulateRecommended())}>
              {running ? <Loader2 size={15} className="animate-spin" /> : <FlaskConical size={15} />}
              Simulate Peak-Hour Strategy
            </button>
          </>
        }
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <KpiCard title="Energy Saved"
                 value={kpi ? `${kpi.saving_kwh} kWh` : "–"}
                 delta={kpi ? `-${kpi.saving_percent}% vs baseline` : undefined}
                 status="success" />
        <KpiCard title="Cost Saved" value={kpi ? fmtVnd(kpi.cost_saving_vnd) : "–"}
                 delta="per simulated day" status="success" />
        <KpiCard title="Peak Reduction"
                 value={kpi ? `${kpi.peak_reduction_kw} kW` : "–"}
                 delta="13:00–16:00 window" status="success" />
        <KpiCard title="Comfort Impact"
                 value={kpi ? `${kpi.comfort_violation_delta_min >= 0 ? "+" : ""}${kpi.comfort_violation_delta_min} min` : "–"}
                 delta="violation delta"
                 status={kpi && kpi.comfort_violation_delta_min > 0 ? "warning" : "success"} />
        <KpiCard title="CO₂ Avoided"
                 value={kpi ? `${kpi.co2_avoided_kg} kg` : "–"}
                 delta="grid factor 0.6766 kg/kWh" status="info" />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_380px]">
        <BaselineOptimizedChart refreshKey={refreshKey} />
        <div className="card px-5 py-4">
          <h3 className="text-sm font-semibold">Simulation summary</h3>
          <ul className="mt-3 space-y-2 text-[13px] text-text-secondary">
            <li>Engine: <b className="text-text-primary">
              {runs[0]?.engine === "energyplus" ? "EnergyPlus batch" : "Synthetic schedule engine"}</b>
              {runs[0]?.engine !== "energyplus" &&
                <span className="text-xs text-text-muted"> (EnergyPlus auto-detected when installed)</span>}
            </li>
            <li>Weather: Hanoi design-day diurnal profile</li>
            <li>Schedules: parsed from greenflow_archetype.idf</li>
            <li>Baseline: fixed schedules, no AI action</li>
            <li>Optimized: identical inputs + agent action schedule overrides</li>
          </ul>
          <p className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">
            This is a what-if counterfactual simulation, not direct real-time
            control of the building.
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_420px]">
        <ScenarioComparisonTable runs={runs} />
        <ActionTraceTimeline actions={actions} />
      </div>
    </div>
  );
}
