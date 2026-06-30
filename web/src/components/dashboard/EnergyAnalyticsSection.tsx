"use client";

import { useEffect, useState } from "react";
import { Zap } from "lucide-react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "@/lib/api";
import KpiCard from "./KpiCard";
import Skeleton from "@/components/shared/Skeleton";
import { usePollMs } from "@/hooks/usePollMs";
import type { Zone } from "@/lib/types";

// load-category palette, reused across donut + stacked area
const CAT: Record<string, string> = {
  HVAC: "#0F766E", Lighting: "#F59E0B", "Plug loads": "#2563EB",
};
const STROKE: Record<string, string> = {
  success: "#16A34A", teal: "#0F766E", warning: "#F59E0B", danger: "#DC2626",
};

function band(s: number) {
  return s >= 85 ? "success" : s >= 70 ? "teal" : s >= 50 ? "warning" : "danger";
}
function bandLabel(s: number) {
  return s >= 85 ? "Excellent" : s >= 70 ? "Efficient" : s >= 50 ? "Average" : "Poor";
}

/** Red→green benchmark gauge for EUI. Center value is raw EUI: lower is better. */
function Gauge({ score, euiAnnual }: { score: number; euiAnnual: number }) {
  const R = 46, C = 2 * Math.PI * R, color = STROKE[band(score)];
  return (
    <div className="relative h-[120px] w-[120px] shrink-0">
      <svg
        viewBox="0 0 116 116"
        className="h-full w-full -rotate-90"
        role="img"
        aria-label={`Energy use intensity ${euiAnnual.toFixed(0)} kWh per square meter per year`}
      >
        <circle cx="58" cy="58" r={R} fill="none" stroke="#E2E8F0" strokeWidth="10" />
        <circle
          cx="58" cy="58" r={R} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={C} strokeDashoffset={C * (1 - score / 100)}
          style={{ transition: "stroke-dashoffset 0.8s ease, stroke 0.4s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[28px] font-semibold leading-none tracking-tight">
          {euiAnnual.toFixed(0)}
        </span>
        <span className="mt-1 text-center text-[9px] font-medium leading-tight text-text-muted">
          kWh/m²/yr
        </span>
      </div>
    </div>
  );
}

const tip = {
  contentStyle: {
    borderRadius: 12, border: "1px solid #E2E8F0", fontSize: 12,
    boxShadow: "0 8px 24px rgba(15,23,42,.08)",
  },
};

/**
 * Energy & performance analytics — a dashboard section: energy KPI tiles, a
 * red→green performance gauge (EUI rating), an energy-mix donut, top consuming
 * zones, and a 24h load profile. All derived from existing APIs (no new
 * endpoint): /timeseries/building, /zones, /kpi/current.
 */
export default function EnergyAnalyticsSection() {
  const [series, setSeries] = useState<any[] | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [kpi, setKpi] = useState<any | null>(null);

  const pollMs = usePollMs(30000);
  useEffect(() => {
    const load = () => {
      api.buildingTimeseries(24).then(setSeries).catch(() => null);
      api.zones().then(setZones).catch(() => null);
      api.kpis().then(setKpi).catch(() => null);
    };
    load();
    const t = setInterval(load, pollMs);
    return () => clearInterval(t);
  }, [pollMs]);

  const ready = !!series && !!kpi && zones.length > 0;
  const energyZones = zones.filter((z) => z.is_energy_counted !== false);

  // ---- derived metrics -----------------------------------------------------
  const totalArea = energyZones.reduce((s, z) => s + (z.area_m2 || 0), 0);
  const kwh = kpi?.kwh || 0;
  const cost = kpi?.cost || 0;
  const peakKw = series?.length ? Math.max(...series.map((p) => p.total_power_kw || 0)) : 0;
  const euiDaily = totalArea ? kwh / totalArea : 0;          // kWh/m²·day
  const euiAnnual = euiDaily * 365;                          // kWh/m²·yr (est.)
  // EUI rating: efficient ≤90 → 100, poor ≥250 → 0 (office benchmark band)
  const score = Math.max(0, Math.min(100, Math.round((100 * (250 - euiAnnual)) / (250 - 90))));

  const sums = (series || []).reduce(
    (a, p) => ({
      HVAC: a.HVAC + (p.hvac_power_kw || 0),
      Lighting: a.Lighting + (p.lighting_power_kw || 0),
      "Plug loads": a["Plug loads"] + (p.plug_power_kw || 0),
    }),
    { HVAC: 0, Lighting: 0, "Plug loads": 0 } as Record<string, number>,
  );
  const mixTotal = sums.HVAC + sums.Lighting + sums["Plug loads"] || 1;
  const mix = (["HVAC", "Lighting", "Plug loads"] as const).map((k) => ({
    name: k, value: sums[k], pct: Math.round((sums[k] / mixTotal) * 100),
  }));

  const topZones = [...energyZones]
    .sort((a, b) => ((b.latest_state?.total_power_kw) || 0) - ((a.latest_state?.total_power_kw) || 0))
    .slice(0, 6)
    .map((z) => ({ name: z.name, kw: Number(((z.latest_state?.total_power_kw) || 0).toFixed(2)) }));

  const chart = (series || []).map((p) => ({
    time: new Date(p.timestamp).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }),
    HVAC: p.hvac_power_kw || 0,
    Lighting: p.lighting_power_kw || 0,
    "Plug loads": p.plug_power_kw || 0,
  }));

  const costStr = cost >= 1e6 ? `${(cost / 1e6).toFixed(2)}M ₫`
    : `${Number(cost).toLocaleString("vi-VN")} ₫`;

  return (
    <section className="mt-4">
      <div className="mb-3 flex items-center gap-2">
        <Zap size={16} className="text-teal" />
        <h2 className="text-sm font-semibold">Energy &amp; performance analytics</h2>
        <span className="text-xs text-text-muted">last 24h · per-category breakdown</span>
      </div>

      {/* energy KPI tiles */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard title="Energy today" value={`${kwh.toFixed(0)} kWh`} loading={!ready}
                 delta="building total" status="normal" />
        <KpiCard title="Cost today" value={costStr} loading={!ready}
                 delta="EVN tariff" status="info" />
        <KpiCard title="Peak demand" value={`${peakKw.toFixed(1)} kW`} loading={!ready}
                 delta="last 24h" status="warning" />
        <KpiCard title="Energy intensity" value={`${euiDaily.toFixed(2)} kWh/m²`} loading={!ready}
                 delta={`≈ ${euiAnnual.toFixed(0)} kWh/m²/yr`}
                 status={score >= 70 ? "success" : score >= 50 ? "warning" : "danger"} />
      </div>

      {/* gauge · donut · top zones */}
      <div className="mt-3 grid gap-4 lg:grid-cols-[0.85fr_0.85fr_1.3fr]">
        {/* performance gauge */}
        <div className="card flex items-center gap-4 px-5 py-4">
          {ready ? <Gauge score={score} euiAnnual={euiAnnual} /> : <Skeleton className="h-[120px] w-[120px] rounded-full" />}
          <div>
            <p className="text-[13px] font-medium text-text-secondary">Energy intensity</p>
            <p className="mt-0.5 text-lg font-semibold" style={{ color: ready ? STROKE[band(score)] : undefined }}>
              {ready ? bandLabel(score) : "…"}
            </p>
            <p className="mt-1 text-[11px] text-text-muted">
              Lower is better · office target ≤90
            </p>
            <p className="mt-0.5 text-[11px] text-text-muted">
              Efficiency score · {ready ? `${score}/100` : "loading…"}
            </p>
          </div>
        </div>

        {/* energy mix donut */}
        <div className="card px-5 py-4">
          <p className="text-[13px] font-medium text-text-secondary">Energy mix</p>
          <div className="flex items-center gap-3">
            <div className="h-[132px] w-[132px] shrink-0">
              {ready ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={mix} dataKey="value" nameKey="name" cx="50%" cy="50%"
                         innerRadius={42} outerRadius={62} paddingAngle={2} stroke="none">
                      {mix.map((m) => <Cell key={m.name} fill={CAT[m.name]} />)}
                    </Pie>
                    <Tooltip {...tip} formatter={(v: any, n: any) => [`${Number(v).toFixed(0)} kW·h-eq`, n]} />
                  </PieChart>
                </ResponsiveContainer>
              ) : <Skeleton className="h-full w-full rounded-full" />}
            </div>
            <ul className="flex-1 space-y-1.5 text-[13px]">
              {mix.map((m) => (
                <li key={m.name} className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1.5 text-text-secondary">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: CAT[m.name] }} />
                    {m.name}
                  </span>
                  <span className="font-semibold">{ready ? `${m.pct}%` : "–"}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* top consuming zones */}
        <div className="card px-5 py-4">
          <p className="text-[13px] font-medium text-text-secondary">Top consuming zones</p>
          <div className="mt-1 h-[132px]">
            {ready ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topZones} layout="vertical" margin={{ top: 2, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="#EEF2F7" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false} unit=" kW" />
                  <YAxis type="category" dataKey="name" width={104} tick={{ fontSize: 10, fill: "#64748B" }}
                         tickLine={false} axisLine={false} />
                  <Tooltip {...tip} formatter={(v: any) => [`${Number(v).toFixed(2)} kW`, "Load"]} />
                  <Bar dataKey="kw" fill="#0F766E" radius={[0, 4, 4, 0]} barSize={12} />
                </BarChart>
              </ResponsiveContainer>
            ) : <Skeleton className="h-full" />}
          </div>
        </div>
      </div>

      {/* 24h load profile (stacked by category) */}
      <div className="card mt-4 px-5 py-4">
        <p className="text-[13px] font-medium text-text-secondary">24-hour load profile</p>
        <div className="mt-2 h-64">
          {ready ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chart} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
                <defs>
                  {(["HVAC", "Lighting", "Plug loads"] as const).map((k) => (
                    <linearGradient key={k} id={`g_${k}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CAT[k]} stopOpacity={0.5} />
                      <stop offset="100%" stopColor={CAT[k]} stopOpacity={0.04} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid stroke="#EEF2F7" vertical={false} />
                <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#94A3B8" }} interval={11}
                       tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} tickLine={false} axisLine={false} unit=" kW" />
                <Tooltip {...tip} formatter={(v: any, n: any) => [`${Number(v).toFixed(1)} kW`, n]} />
                {(["Plug loads", "Lighting", "HVAC"] as const).map((k) => (
                  <Area key={k} type="monotone" dataKey={k} name={k} stackId="1"
                        stroke={CAT[k]} strokeWidth={1.6} fill={`url(#g_${k})`} dot={false} />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          ) : <Skeleton className="h-full" />}
        </div>
      </div>
    </section>
  );
}
