"use client";

import { useEffect, useState, type ReactNode } from "react";
import { CircleHelp, Zap } from "lucide-react";
import {
  Area, AreaChart, CartesianGrid, Cell, Pie, PieChart,
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

function InfoTip({ text }: { text: string }) {
  return (
    <span
      className="group/help relative inline-flex text-slate-400 transition hover:text-teal focus-visible:text-teal"
      tabIndex={0}
    >
      <CircleHelp size={15} aria-hidden="true" />
      <span className="pointer-events-none invisible absolute right-0 top-6 z-50 w-72 rounded-xl border border-slate-200 bg-slate-950 px-3 py-2 text-[11px] font-medium leading-relaxed text-white opacity-0 shadow-xl transition group-hover/help:visible group-hover/help:opacity-100 group-focus/help:visible group-focus/help:opacity-100">
        {text}
      </span>
    </span>
  );
}

function CardTitle({ children, tipText }: { children: ReactNode; tipText: string }) {
  return (
    <div className="mb-1 flex items-center justify-between gap-3">
      <p className="text-[13px] font-medium text-text-secondary">{children}</p>
      <InfoTip text={tipText} />
    </div>
  );
}

/**
 * Energy analytics — a dashboard section: energy KPI tiles, a red→green
 * benchmark gauge (EUI rating), a load-share donut, top consuming
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
  const timestepHours = series && series.length > 1
    ? Math.max(0, (new Date(series[1].timestamp).getTime() - new Date(series[0].timestamp).getTime()) / 3600000)
    : 0.25;
  // EUI rating: efficient ≤90 → 100, poor ≥250 → 0 (office benchmark band)
  const score = Math.max(0, Math.min(100, Math.round((100 * (250 - euiAnnual)) / (250 - 90))));

  const sums = (series || []).reduce(
    (a, p) => ({
      HVAC: a.HVAC + ((p.hvac_power_kw || 0) * timestepHours),
      Lighting: a.Lighting + ((p.lighting_power_kw || 0) * timestepHours),
      "Plug loads": a["Plug loads"] + ((p.plug_power_kw || 0) * timestepHours),
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
    .map((z) => ({
      name: z.name,
      kw: Number(((z.latest_state?.total_power_kw) || 0).toFixed(2)),
    }));
  const topZoneMaxKw = Math.max(1, ...topZones.map((zone) => zone.kw));

  const chart = (series || []).map((p) => ({
    time: new Date(p.timestamp).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }),
    HVAC: p.hvac_power_kw || 0,
    Lighting: p.lighting_power_kw || 0,
    "Plug loads": p.plug_power_kw || 0,
  }));

  const costStr = cost >= 1e6 ? `${(cost / 1e6).toFixed(2)}M ₫`
    : `${Number(cost).toLocaleString("vi-VN")} ₫`;
  const euiExplanation = `Energy use intensity run-rate = today's energy divided by counted floor area, then annualized. Current inputs: ${kwh.toFixed(0)} kWh today / ${totalArea.toFixed(0)} m² = ${euiDaily.toFixed(2)} kWh/m²/day, or about ${euiAnnual.toFixed(0)} kWh/m²/year. Lower is better; office target is ≤90 kWh/m²/year.`;
  const mixExplanation = `Load share uses the last 24h building timeseries and integrates each power category by timestep. HVAC, lighting, and plug-load kWh are compared as percentages of the category total.`;
  const topZonesExplanation = `Top consuming zones ranks counted zones by their latest total_power_kw from the backend zone state. This is an instantaneous load view, not a daily kWh total.`;
  const loadProfileExplanation = `24-hour load profile comes from /timeseries/building and shows HVAC, lighting, and plug-load power over the latest replay window.`;
  const updatedAt = kpi?.timestamp;

  return (
    <section className="mt-4">
      <div className="mb-3 flex items-center gap-2">
        <Zap size={16} className="text-teal" />
        <h2 className="text-sm font-semibold">Energy analytics</h2>
        <span className="text-xs text-text-muted">today totals · last 24h load profile</span>
      </div>

      {/* energy KPI tiles */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard title="Energy used today" value={`${kwh.toFixed(0)} kWh`} loading={!ready}
                 delta="calendar day-to-date" status="normal"
                 help={{
                   summary: "Total calendar-day energy from counted building zones at the current replay anchor.",
                   statusReason: `Backend value from /kpi/current: ${kwh.toFixed(0)} kWh today.`,
                   thresholds: "Use this with the EUI card to judge whether today's consumption is normal for the modeled floor area.",
                   timestamp: updatedAt,
                 }} />
        <KpiCard title="Cost today" value={costStr} loading={!ready}
                 delta="calendar day-to-date" status="info"
                 help={{
                   summary: "Estimated day-to-date electricity cost for the same counted energy scope.",
                   statusReason: `Backend value from /kpi/current: ${costStr}.`,
                   thresholds: "This is an operational estimate using the configured tariff, not a utility-bill settlement.",
                   timestamp: updatedAt,
                 }} />
        <KpiCard title="Peak demand, last 24h" value={`${peakKw.toFixed(1)} kW`} loading={!ready}
                 delta="last 24h" status="warning"
                 help={{
                   summary: "Maximum total building load observed in the last 24-hour building timeseries.",
                   statusReason: `Current 24h peak is ${peakKw.toFixed(1)} kW.`,
                   thresholds: "High peak demand increases demand charges and drives the Energy / Demand risk score.",
                   timestamp: updatedAt,
                 }} />
        <KpiCard title="EUI run-rate" value={`${euiDaily.toFixed(2)} kWh/m²`} loading={!ready}
                 delta={`annualized ≈ ${euiAnnual.toFixed(0)} kWh/m²/yr`}
                 status={score >= 70 ? "success" : score >= 50 ? "warning" : "danger"}
                 help={{
                   summary: "Energy Use Intensity run-rate normalizes today's energy by counted floor area.",
                   statusReason: `${kwh.toFixed(0)} kWh / ${totalArea.toFixed(0)} m² = ${euiDaily.toFixed(2)} kWh/m² today; annualized to about ${euiAnnual.toFixed(0)} kWh/m²/year.`,
                   thresholds: "Lower is better. Office target used here: <=90 kWh/m²/year; poor band approaches 250 kWh/m²/year.",
                   timestamp: updatedAt,
                 }} />
      </div>

      {/* gauge · donut · top zones */}
      <div className="mt-3 grid gap-4 lg:grid-cols-[0.85fr_0.85fr_1.3fr]">
        {/* performance gauge */}
        <div className="card px-5 py-4">
          <div className="flex justify-end">
            <InfoTip text={euiExplanation} />
          </div>
          <div className="flex items-center gap-4">
          {ready ? <Gauge score={score} euiAnnual={euiAnnual} /> : <Skeleton className="h-[120px] w-[120px] rounded-full" />}
          <div>
            <p className="text-[13px] font-medium text-text-secondary">EUI run-rate</p>
            <p className="mt-0.5 text-lg font-semibold" style={{ color: ready ? STROKE[band(score)] : undefined }}>
              {ready ? bandLabel(score) : "…"}
            </p>
            <p className="mt-1 text-[11px] text-text-muted">
              Lower is better · office target ≤90
            </p>
            <p className="mt-0.5 text-[11px] text-text-muted">
              Annualized from today's use · {ready ? `${score}/100` : "loading…"}
            </p>
          </div>
          </div>
        </div>

        {/* load-share donut */}
        <div className="card px-5 py-4">
          <CardTitle tipText={mixExplanation}>Load share, last 24h</CardTitle>
          <div className="flex items-center gap-3">
            <div className="h-[132px] w-[132px] shrink-0">
              {ready ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={mix} dataKey="value" nameKey="name" cx="50%" cy="50%"
                         innerRadius={42} outerRadius={62} paddingAngle={2} stroke="none">
                      {mix.map((m) => <Cell key={m.name} fill={CAT[m.name]} />)}
                    </Pie>
                    <Tooltip {...tip} formatter={(v: any, n: any) => [`${Number(v).toFixed(1)} kWh`, n]} />
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
          <CardTitle tipText={topZonesExplanation}>Top consuming zones</CardTitle>
          <div className="mt-2 h-[228px]">
            {ready ? (
              <div className="flex h-full flex-col justify-between">
                {topZones.map((zone, index) => (
                  <div
                    key={`${zone.name}-${index}`}
                    className="grid min-h-[30px] grid-cols-[minmax(136px,190px)_1fr_56px] items-center gap-3"
                    title={zone.name}
                  >
                    <p className="text-[10.5px] font-medium leading-tight text-slate-600">
                      {zone.name}
                    </p>
                    <div className="h-3 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-[#0F766E]"
                        style={{ width: `${Math.max(4, (zone.kw / topZoneMaxKw) * 100)}%` }}
                      />
                    </div>
                    <p className="text-right text-[10.5px] font-semibold tabular-nums text-slate-500">
                      {zone.kw.toFixed(1)}
                    </p>
                  </div>
                ))}
              </div>
            ) : <Skeleton className="h-full" />}
          </div>
        </div>
      </div>

      {/* 24h load profile (stacked by category) */}
      <div className="card mt-4 px-5 py-4">
        <CardTitle tipText={loadProfileExplanation}>24-hour load profile</CardTitle>
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
