"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Boxes, ChevronRight, FlaskConical, GitCompareArrows, Loader2 } from "lucide-react";
import { animate, motion, useReducedMotion } from "motion/react";
import PageHeader from "@/components/shell/PageHeader";
import BaselineOptimizedChart from "@/components/simulation/BaselineOptimizedChart";
import ScenarioComparisonTable from "@/components/simulation/ScenarioComparisonTable";
import ActionTraceTimeline from "@/components/simulation/ActionTraceTimeline";
import ValidationPanel from "@/components/simulation/ValidationPanel";
import { useAgentRun } from "@/hooks/useAgentRun";
import { api } from "@/lib/api";
import { fmtVnd } from "@/lib/format";
import type { ComparisonKpi, SimulationRun } from "@/lib/types";

const TONE: Record<string, string> = {
  success: "#16A34A", teal: "#0F766E", info: "#2563EB", warning: "#F59E0B",
};

/** Animate a number from its previous value to the target (premium count-up). */
function useCountUp(target: number, reduce: boolean): number {
  const [d, setD] = useState(target);
  const prev = useRef(0);
  useEffect(() => {
    if (reduce) { setD(target); prev.current = target; return; }
    const controls = animate(prev.current, target, {
      duration: 0.9, ease: [0.16, 1, 0.3, 1], onUpdate: (v) => setD(v),
    });
    prev.current = target;
    return () => controls.stop();
  }, [target, reduce]);
  return d;
}

/** One elevated savings tile with a count-up headline number. */
function SavingsStat({ label, value, format, delta, tone = "teal", index }: {
  label: string; value: number | null | undefined;
  format: (v: number) => string; delta?: string;
  tone?: keyof typeof TONE; index: number;
}) {
  const reduce = useReducedMotion();
  const display = useCountUp(value ?? 0, !!reduce);
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 26, delay: index * 0.06 }}
      className="card-elevated flex flex-col gap-1 px-5 py-4"
    >
      <span className="text-[12.5px] font-medium text-text-secondary">{label}</span>
      <span className="text-[27px] font-semibold leading-tight tracking-tight tabular-nums"
            style={{ color: value == null ? undefined : TONE[tone] }}>
        {value == null ? "·" : format(display)}
      </span>
      {delta && <span className="text-[11.5px] text-text-muted">{delta}</span>}
    </motion.div>
  );
}

const TARGET_LABEL: Record<string, string> = {
  building_total_kw: "Building demand", zone_total_kw: "Zone power",
  hvac_power_kw: "Zone HVAC power",
};

/** The forecast models behind the simulation, mirrored from the MLflow registry. */
function ModelRegistryCard() {
  const [info, setInfo] = useState<any>(null);
  useEffect(() => { api.modelInfo().then(setInfo).catch(() => null); }, []);
  if (!info?.models?.length) return null;
  return (
    <div className="card-elevated mt-4 px-5 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <Boxes size={16} className="text-teal" />
        <h3 className="text-sm font-semibold tracking-tight">Forecast models</h3>
        <span className="rounded-full bg-teal-soft px-2 py-0.5 text-[11px] font-medium text-teal">
          MLflow registry
        </span>
        <span className="ml-auto truncate text-[11px] text-text-muted">{info.engine}</span>
      </div>
      <div className="mt-3 grid gap-2.5 sm:grid-cols-3">
        {info.models.map((m: any) => (
          <div key={m.registry_name} className="rounded-xl border border-border/55 bg-surface px-3.5 py-3">
            <p className="text-[12.5px] font-semibold">{TARGET_LABEL[m.target] || m.target}</p>
            <div className="mt-1.5 flex items-baseline gap-2">
              <span className="text-[22px] font-semibold leading-none tracking-tight text-success tabular-nums">
                {(m.metrics?.r2 ?? 0).toFixed(2)}
              </span>
              <span className="text-[11px] text-text-muted">R² · MAE {m.metrics?.mae_kw} kW</span>
            </div>
            <p className="mt-1.5 truncate text-[10.5px] text-text-muted">{m.registry_name}</p>
            <p className="text-[10.5px] text-text-muted">test: {m.split}</p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11px] leading-relaxed text-text-muted">
        Derived signals: comfort risk and peak risk (deterministic rules), temperature (thermal surrogate).
      </p>
    </div>
  );
}

/** Heavy fade-up as a section enters the viewport. */
function Reveal({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

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
        subtitle="Counterfactual proof: same weather and occupancy, only the agent's actions differ."
        actions={
          <>
            <motion.button whileTap={{ scale: 0.96 }} className="btn-secondary" disabled={running}
                           onClick={() => start(() => api.compareBaseline())}>
              <GitCompareArrows size={15} /> Compare baseline
            </motion.button>
            <motion.button whileTap={{ scale: 0.96 }} className="btn-primary" disabled={running}
                           onClick={() => start(() => api.simulateRecommended())}>
              {running ? <Loader2 size={15} className="animate-spin" /> : <FlaskConical size={15} />}
              Simulate peak-hour strategy
            </motion.button>
          </>
        }
      />

      {/* savings headline: elevated tiles with count-up numbers */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <SavingsStat index={0} label="Energy saved" value={kpi?.saving_kwh}
                     format={(v) => `${Math.round(v)} kWh`}
                     delta={kpi ? `-${kpi.saving_percent}% vs baseline` : undefined} tone="success" />
        <SavingsStat index={1} label="Cost saved" value={kpi?.cost_saving_vnd}
                     format={(v) => fmtVnd(Math.round(v))} delta="per simulated day" tone="success" />
        <SavingsStat index={2} label="Peak reduction" value={kpi?.peak_reduction_kw}
                     format={(v) => `${v.toFixed(1)} kW`} delta="13:00-16:00 window" tone="teal" />
        <SavingsStat index={3} label="Comfort impact" value={kpi?.comfort_violation_delta_min}
                     format={(v) => `${v >= 0 ? "+" : ""}${Math.round(v)} min`} delta="violation delta"
                     tone={kpi && kpi.comfort_violation_delta_min > 0 ? "warning" : "success"} />
        <SavingsStat index={4} label="CO₂ avoided" value={kpi?.co2_avoided_kg}
                     format={(v) => `${Math.round(v)} kg`} delta="grid factor 0.6766 kg/kWh" tone="info" />
      </div>

      <ModelRegistryCard />

      {/* proof: 24h profile + how it's simulated */}
      <Reveal className="mt-4 grid gap-4 xl:grid-cols-[1fr_380px]">
        <BaselineOptimizedChart refreshKey={refreshKey} />
        <div className="card-elevated px-5 py-4">
          <h3 className="text-sm font-semibold tracking-tight">How this is simulated</h3>
          <ul className="mt-3 space-y-2 text-[13px] text-text-secondary">
            <li>Engine: <b className="text-text-primary">
              {runs[0]?.engine === "energyplus" ? "EnergyPlus batch" : "Synthetic schedule engine"}</b>
              {runs[0]?.engine !== "energyplus" &&
                <span className="text-xs text-text-muted"> (EnergyPlus auto-detected when installed)</span>}
            </li>
            <li>Weather: Hanoi design-day diurnal profile</li>
            <li>Schedules: parsed from greenflow_archetype.idf</li>
            <li>Baseline: fixed schedules, no AI action</li>
            <li>Optimized: identical inputs plus the agent's action overrides</li>
          </ul>
          <p className="mt-4 rounded-xl bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-700">
            A what-if counterfactual simulation, not direct real-time control of the building.
          </p>
        </div>
      </Reveal>

      {/* scenarios + the action trace that produced them */}
      <Reveal className="mt-4 grid gap-4 lg:grid-cols-[1fr_420px]">
        <ScenarioComparisonTable runs={runs} />
        <ActionTraceTimeline actions={actions} />
      </Reveal>

      {/* validation tucked away so the proof stays the focus */}
      <details className="group mt-4">
        <summary className="flex w-fit cursor-pointer list-none items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium text-text-secondary transition hover:bg-surface-muted">
          <ChevronRight size={14} className="text-text-muted transition group-open:rotate-90" />
          Validation &amp; methodology
        </summary>
        <div className="mt-3">
          <ValidationPanel />
        </div>
      </details>
    </div>
  );
}
