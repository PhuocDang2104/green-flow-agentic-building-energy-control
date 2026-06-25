"use client";

import { useEffect, useState } from "react";
import {
  Area, AreaChart, CartesianGrid, Legend, ReferenceArea, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "@/lib/api";
import Skeleton from "@/components/shared/Skeleton";
import EmptyState from "@/components/shared/EmptyState";

const METRICS = [
  { id: "total_power_kw", label: "Total" },
  { id: "hvac_power_kw", label: "HVAC" },
  { id: "lighting_power_kw", label: "Lighting" },
  { id: "zone_temperature_c", label: "Temperature" },
];

export default function BaselineOptimizedChart({ refreshKey }: { refreshKey?: number }) {
  const [metric, setMetric] = useState("total_power_kw");
  const [data, setData] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.comparisonSeries(metric)
      .then((res) => {
        setData(res.series.map((p) => ({
          ...p,
          time: new Date(p.timestamp).toLocaleTimeString("en-GB",
            { hour: "2-digit", minute: "2-digit" }),
          hour: new Date(p.timestamp).getHours(),
        })));
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [metric, refreshKey]);

  return (
    <div className="card-elevated px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Baseline vs optimized</h3>
        <div className="flex gap-1">
          {METRICS.map((m) => (
            <button
              key={m.id}
              onClick={() => setMetric(m.id)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition
                ${metric === m.id ? "bg-teal text-white" : "text-text-secondary hover:bg-surface-muted"}`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-3 h-72">
        {loading && <Skeleton className="h-full" />}
        {!loading && !data && (
          <EmptyState title="No comparison yet" hint="Run an optimization first." />
        )}
        {!loading && data && (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
              <defs>
                <linearGradient id="base" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#94A3B8" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#94A3B8" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="opt" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0F766E" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#0F766E" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#EEF2F7" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#94A3B8" }}
                     interval={11} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} tickLine={false}
                     axisLine={false} />
              <Tooltip
                contentStyle={{ borderRadius: 12, border: "1px solid #E2E8F0",
                  fontSize: 12, boxShadow: "0 8px 24px rgba(15,23,42,.08)" }}
                formatter={(v: any, name: any) => [Number(v).toFixed(2), name]}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {/* peak window 13:00–16:00 */}
              <ReferenceArea
                x1={data.find((d) => d.hour === 13)?.time}
                x2={data.find((d) => d.hour === 16)?.time}
                fill="#F59E0B" fillOpacity={0.07}
              />
              <Area type="monotone" dataKey="baseline" name="Baseline"
                    stroke="#94A3B8" strokeWidth={1.8} fill="url(#base)" dot={false} />
              <Area type="monotone" dataKey="optimized" name="Optimized"
                    stroke="#0F766E" strokeWidth={2} fill="url(#opt)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
