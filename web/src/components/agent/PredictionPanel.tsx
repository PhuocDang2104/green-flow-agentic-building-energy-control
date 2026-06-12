"use client";

import { fmtPct } from "@/lib/format";
import StatusPill from "@/components/shared/StatusPill";
import EmptyState from "@/components/shared/EmptyState";
import type { AgentRun } from "@/lib/types";

export default function PredictionPanel({ run }: { run: AgentRun | null }) {
  const state = run?.state_json;
  const forecast = state?.forecast_result;
  if (!forecast) {
    return (
      <div className="card px-5 py-4">
        <h3 className="text-sm font-semibold">Prediction</h3>
        <EmptyState title="No forecast yet" hint="Run Prediction or Run Optimization." />
      </div>
    );
  }
  const peak = state?.peak_risk || {};
  const highRisk: string[] = forecast.high_comfort_risk_zones || [];
  return (
    <div className="card px-5 py-4">
      <h3 className="text-sm font-semibold">Prediction</h3>
      <div className="mt-3 grid grid-cols-2 gap-2 text-[13px]">
        <Cell label="Load now" value={`${forecast.building_load_now_kw ?? "–"} kW`} />
        <Cell label={`Load +${state?.forecast_horizon_minutes ?? 60}m`}
              value={`${forecast.building_load_forecast_kw ?? "–"} kW`} />
        <Cell label="Peak risk" value={<StatusPill status={peak.level} />} />
        <Cell label="Confidence" value={fmtPct(state?.forecast_confidence)} />
      </div>
      <p className="mt-3 text-xs text-text-muted">
        {highRisk.length
          ? `High comfort-risk zones: ${highRisk.join(", ")}`
          : "No high comfort-risk zones in the forecast window."}
      </p>
      <p className="mt-1 text-[11px] text-text-muted">
        Model: {state?.prediction_explanation?.model || "schedule-aware persistence"}
      </p>
    </div>
  );
}

function Cell({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl bg-surface-muted/60 px-3 py-2">
      <p className="text-[11px] text-text-muted">{label}</p>
      <div className="text-[15px] font-semibold">{value}</div>
    </div>
  );
}
