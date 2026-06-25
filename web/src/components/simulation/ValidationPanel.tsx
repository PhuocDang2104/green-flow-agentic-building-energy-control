"use client";

import { useEffect, useState } from "react";
import {
  Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { ShieldCheck, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import KpiCard from "@/components/dashboard/KpiCard";
import Skeleton from "@/components/shared/Skeleton";
import EmptyState from "@/components/shared/EmptyState";
import type { ValidationResult } from "@/lib/types";

const VERDICT_STATUS: Record<string, "success" | "warning" | "danger"> = {
  "well calibrated": "success",
  "acceptable, minor drift": "warning",
  "needs recalibration": "danger",
};

export default function ValidationPanel() {
  const [dayType, setDayType] = useState<"weekday" | "weekend">("weekday");
  const [data, setData] = useState<ValidationResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    api.validateBaseline(dayType === "weekend")
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [dayType]);

  const status = data ? VERDICT_STATUS[data.verdict] ?? "info" : "info";

  return (
    <div className="card-elevated px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">Model validation</h3>
          <p className="text-xs text-text-muted">
            Replays the no-action baseline against a real historical day to prove it&apos;s calibrated.
          </p>
        </div>
        <div className="flex gap-1">
          {(["weekday", "weekend"] as const).map((d) => (
            <button key={d} onClick={() => setDayType(d)}
                    className={`rounded-full px-3 py-1 text-xs font-medium capitalize transition
                      ${dayType === d ? "bg-teal text-white" : "text-text-secondary hover:bg-surface-muted"}`}>
              {d}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="mt-3 h-72"><Skeleton className="h-full" /></div>}
      {!loading && (error || !data) && (
        <div className="mt-3 h-72">
          <EmptyState title="No full historical day yet" hint="Let the replay clock run a full day, then check back." />
        </div>
      )}

      {!loading && data && (
        <>
          <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
            <KpiCard title="Backtest day" value={data.date}
                     delta={data.is_weekend ? "weekend" : "weekday"} status="info" />
            <KpiCard title="MAPE" value={data.mape_pct !== null ? `${data.mape_pct}%` : "–"}
                     delta="vs real telemetry" status={status} />
            <KpiCard title="RMSE" value={`${data.rmse_kw} kW`}
                     delta="building total" status={status} />
            <KpiCard title="Peak alignment"
                     value={data.peak_real_time === data.peak_sim_time ? "exact" : "offset"}
                     delta={`real ${data.peak_real_time ?? "–"} / sim ${data.peak_sim_time ?? "–"}`}
                     status={data.peak_real_time === data.peak_sim_time ? "success" : "warning"} />
          </div>

          <div className={`mt-3 flex items-center gap-2 rounded-xl px-3 py-2 text-xs
            ${status === "success" ? "bg-teal-soft text-teal"
              : status === "warning" ? "bg-amber-50 text-amber-700" : "bg-red-50 text-danger"}`}>
            {status === "danger" ? <ShieldAlert size={14} /> : <ShieldCheck size={14} />}
            Baseline engine is <b>{data.verdict}</b> against {data.date} telemetry
            ({data.real_kwh} kWh real vs {data.sim_kwh} kWh simulated).
          </div>

          <div className="mt-3 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.series} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
                <defs>
                  <linearGradient id="real" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#0F766E" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#0F766E" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#EEF2F7" vertical={false} />
                <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#94A3B8" }}
                       interval={11} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ borderRadius: 12, border: "1px solid #E2E8F0",
                    fontSize: 12, boxShadow: "0 8px 24px rgba(15,23,42,.08)" }}
                  formatter={(v: any, name: any) => [Number(v).toFixed(1), name]}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Area type="monotone" dataKey="real_kw" name="Real telemetry"
                      stroke="#0F766E" strokeWidth={2} fill="url(#real)" dot={false} />
                <Area type="monotone" dataKey="sim_kw" name="Synthetic baseline"
                      stroke="#94A3B8" strokeWidth={1.8} fill="none" strokeDasharray="4 3" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-3 max-h-44 overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-white text-text-muted">
                <tr>
                  <th className="py-1 font-medium">Zone</th>
                  <th className="py-1 font-medium">Real kWh</th>
                  <th className="py-1 font-medium">Sim kWh</th>
                  <th className="py-1 font-medium">Error</th>
                </tr>
              </thead>
              <tbody>
                {data.zones.map((z) => (
                  <tr key={z.zone_key} className="border-t border-border/60">
                    <td className="py-1.5">{z.zone_name}</td>
                    <td className="py-1.5">{z.real_kwh}</td>
                    <td className="py-1.5">{z.sim_kwh}</td>
                    <td className={`py-1.5 font-medium ${
                      (z.error_pct ?? 0) > 20 ? "text-danger"
                        : (z.error_pct ?? 0) > 8 ? "text-warning" : "text-teal"}`}>
                      {z.error_pct !== null ? `${z.error_pct}%` : "–"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
