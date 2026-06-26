"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Layers, Loader2, Target } from "lucide-react";
import { api } from "@/lib/api";
import type { SimulationRun } from "@/lib/types";

const METRICS = [
  { id: "total_power_kw", label: "Total power" },
  { id: "hvac_power_kw", label: "HVAC power" },
  { id: "lighting_power_kw", label: "Lighting" },
] as const;

const WINDOWS = [
  { id: "day", label: "Full day", lo: 0, hi: 24 },
  { id: "office", label: "Office 7-19h", lo: 7, hi: 19 },
  { id: "peak", label: "Peak 13-16h", lo: 13, hi: 16 },
] as const;

// distinct, colour-blind-safe series colours; reference scenario is drawn dashed
const COLORS = ["#0F766E", "#DC2626", "#2563EB", "#F59E0B", "#7C3AED", "#0891B2"];
const KIND: Record<string, string> = {
  baseline: "Baseline", agent: "Optimized", peak_strategy: "Peak strategy",
};

function vnParts(ts: string) {
  const d = new Date(ts);
  const o = { timeZone: "Asia/Ho_Chi_Minh", hour12: false } as const;
  return {
    hour: Number(d.toLocaleString("en-GB", { ...o, hour: "2-digit" })),
    label: d.toLocaleString("en-GB", { ...o, hour: "2-digit", minute: "2-digit" }),
  };
}
function runLabel(r: SimulationRun) {
  const t = new Date(r.started_at).toLocaleString("en-GB",
    { timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", minute: "2-digit", hour12: false });
  return `${KIND[r.run_kind] || r.run_kind} · ${t}`;
}
const num = (v: number | undefined, d = 1) => (v == null ? "·" : v.toFixed(d));

function Delta({ value, invert }: { value: number | null; invert?: boolean }) {
  if (value == null || !isFinite(value)) return <span className="text-text-muted">·</span>;
  const good = invert ? value > 0 : value < 0; // lower energy/peak = good
  const cls = Math.abs(value) < 0.05 ? "text-text-muted" : good ? "text-success" : "text-danger";
  return <span className={`tabular-nums ${cls}`}>{value >= 0 ? "+" : ""}{value.toFixed(1)}%</span>;
}

/**
 * Scenario comparison workbench: pick any simulation runs, set one as the
 * reference, choose a metric and a time window, then overlay their 24h profiles
 * and read the metric deltas against the reference. Mirrors how building-sim
 * tools (EnergyPlus result viewers, DesignBuilder) browse and compare cases.
 */
export default function ScenarioWorkbench() {
  const [runs, setRuns] = useState<SimulationRun[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [refId, setRefId] = useState<string | null>(null);
  const [metric, setMetric] = useState<string>("total_power_kw");
  const [windowId, setWindowId] = useState<string>("day");
  const [series, setSeries] = useState<Record<string, { timestamp: string; value: number }[]>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.simulations().then((rs) => {
      setRuns(rs);
      const base = rs.find((r) => r.run_kind === "baseline");
      const opt = rs.find((r) => r.run_kind !== "baseline");
      const sel = [base?.id, opt?.id].filter(Boolean) as string[];
      setSelected(sel);
      setRefId(base?.id ?? sel[0] ?? null);
    }).catch(() => null);
  }, []);

  useEffect(() => {
    if (!selected.length) { setSeries({}); return; }
    let stop = false;
    setLoading(true);
    Promise.all(selected.map((id) =>
      api.runSeries(id, metric).then((s) => [id, s] as const).catch(() => [id, []] as const)))
      .then((pairs) => { if (!stop) setSeries(Object.fromEntries(pairs)); })
      .finally(() => { if (!stop) setLoading(false); });
    return () => { stop = true; };
  }, [selected, metric]);

  const win = WINDOWS.find((w) => w.id === windowId)!;
  const runById = useMemo(() => Object.fromEntries(runs.map((r) => [r.id, r])), [runs]);
  const color = (id: string) => COLORS[selected.indexOf(id) % COLORS.length];

  const chart = useMemo(() => {
    const byTs: Record<string, any> = {};
    for (const id of selected) {
      for (const p of series[id] || []) {
        const { hour, label } = vnParts(p.timestamp);
        if (hour < win.lo || hour >= win.hi) continue;
        (byTs[p.timestamp] ||= { time: label })[id] = p.value;
      }
    }
    return Object.keys(byTs).sort().map((k) => byTs[k]);
  }, [series, selected, win]);

  const rows = useMemo(() => selected.map((id) => {
    const r = runById[id]; const s = series[id] || [];
    const winE = s.filter((p) => { const h = vnParts(p.timestamp).hour; return h >= win.lo && h < win.hi; })
      .reduce((a, p) => a + (p.value || 0), 0) * 0.5; // 30-min steps -> kWh
    const t = r?.totals;
    return { id, label: r ? runLabel(r) : id, winE,
             energy: t?.energy_kwh, peak: t?.peak_demand_kw, comfort: t?.comfort_violation_minutes,
             actions: (r?.actions_json || []).length };
  }), [selected, series, runById, win]);
  const ref = rows.find((x) => x.id === refId) || rows[0];
  const pct = (v?: number, base?: number) => (v == null || !base ? null : ((v - base) / base) * 100);

  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]).slice(-6));

  return (
    <div className="card-elevated mt-4 px-5 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <Layers size={16} className="text-teal" />
        <h3 className="text-sm font-semibold tracking-tight">Scenario comparison</h3>
        {loading && <Loader2 size={13} className="animate-spin text-text-muted" />}
        <div className="ml-auto flex items-center gap-2">
          <select value={metric} onChange={(e) => setMetric(e.target.value)}
                  className="rounded-lg border border-border px-2 py-1 text-[12px]">
            {METRICS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
          </select>
          <div className="flex rounded-lg border border-border p-0.5 text-[11.5px]">
            {WINDOWS.map((w) => (
              <button key={w.id} onClick={() => setWindowId(w.id)}
                      className={`rounded-md px-2 py-0.5 font-medium transition ${windowId === w.id ? "bg-teal text-white" : "text-text-secondary hover:bg-surface-muted"}`}>
                {w.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-3 grid gap-4 lg:grid-cols-[220px_1fr]">
        {/* scenario picker */}
        <div className="max-h-[300px] space-y-1 overflow-y-auto pr-0.5">
          {runs.length === 0 && (
            <p className="px-1 py-2 text-[12px] text-text-muted">No simulation runs yet. Run a comparison.</p>
          )}
          {runs.map((r) => {
            const on = selected.includes(r.id);
            return (
              <div key={r.id} className={`flex items-center gap-2 rounded-lg px-2 py-1.5 ${on ? "bg-surface-muted/60" : ""}`}>
                <input type="checkbox" checked={on} onChange={() => toggle(r.id)}
                       className="h-3.5 w-3.5 accent-teal" />
                <span className="h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ background: on ? color(r.id) : "#CBD5E1" }} />
                <button onClick={() => toggle(r.id)} className="min-w-0 flex-1 text-left">
                  <p className="truncate text-[12px] font-medium">{runLabel(r)}</p>
                  <p className="text-[10.5px] text-text-muted">
                    {num(r.totals?.energy_kwh, 0)} kWh · {(r.actions_json || []).length} actions
                  </p>
                </button>
                <button onClick={() => setRefId(r.id)} title="Set as reference"
                        className={`shrink-0 rounded p-0.5 ${refId === r.id ? "text-teal" : "text-text-muted hover:text-teal"}`}>
                  <Target size={13} />
                </button>
              </div>
            );
          })}
        </div>

        {/* overlay chart */}
        <div className="h-[300px]">
          {chart.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart} margin={{ top: 6, right: 10, bottom: 0, left: -16 }}>
                <CartesianGrid stroke="#EEF2F7" vertical={false} />
                <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#94A3B8" }} interval="preserveStartEnd"
                       minTickGap={28} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false} unit=" kW" />
                <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #E2E8F0", fontSize: 12 }}
                         formatter={(v: any, n: any) => [`${Number(v).toFixed(2)} kW`, runById[n] ? runLabel(runById[n]) : n]} />
                {selected.map((id) => (
                  <Line key={id} type="monotone" dataKey={id} name={id} stroke={color(id)}
                        strokeWidth={id === refId ? 2 : 1.8} strokeDasharray={id === refId ? "5 4" : undefined}
                        dot={false} connectNulls />
                ))}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="grid h-full place-items-center text-[12px] text-text-muted">
              Select one or more scenarios to compare.
            </div>
          )}
        </div>
      </div>

      {/* comparison table: scenarios x metrics, Δ vs reference */}
      {rows.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-text-muted">
                <th className="py-1.5 font-medium">Scenario</th>
                <th className="py-1.5 text-right font-medium">Window kWh</th>
                <th className="py-1.5 text-right font-medium">Day kWh</th>
                <th className="py-1.5 text-right font-medium">Δ energy</th>
                <th className="py-1.5 text-right font-medium">Peak kW</th>
                <th className="py-1.5 text-right font-medium">Δ peak</th>
                <th className="py-1.5 text-right font-medium">Comfort min</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {rows.map((x) => (
                <tr key={x.id}>
                  <td className="py-1.5">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full" style={{ background: color(x.id) }} />
                      {x.label}{x.id === refId && <span className="ml-1 text-[10px] text-teal">ref</span>}
                    </span>
                  </td>
                  <td className="py-1.5 text-right tabular-nums">{x.winE.toFixed(1)}</td>
                  <td className="py-1.5 text-right tabular-nums">{num(x.energy, 1)}</td>
                  <td className="py-1.5 text-right"><Delta value={pct(x.energy, ref?.energy)} /></td>
                  <td className="py-1.5 text-right tabular-nums">{num(x.peak, 2)}</td>
                  <td className="py-1.5 text-right"><Delta value={pct(x.peak, ref?.peak)} /></td>
                  <td className="py-1.5 text-right tabular-nums">{x.comfort ?? "·"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[10.5px] text-text-muted">
            Δ vs reference (dashed line). Same weather and occupancy across scenarios; only actions differ.
          </p>
        </div>
      )}
    </div>
  );
}
