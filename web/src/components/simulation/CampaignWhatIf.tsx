"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { BarChart3, CalendarDays, Info, Loader2, Sun, Zap } from "lucide-react";
import { motion } from "motion/react";
import { api } from "@/lib/api";
import { fmtVnd } from "@/lib/format";
import { useTutorialStore } from "@/components/tutorial/tutorialStore";

type WhatIfData = Awaited<ReturnType<typeof api.whatifCache>>;
type DateRange = { start: string; end: string };
type MetricConfig = {
  id: string;
  label: string;
  shortLabel: string;
  unit: string;
  base: string;
  opt: string;
  summary: string;
  meaning: string;
  band?: { y1: number; y2: number; label: string };
  thresholds?: readonly number[];
};

const PRECOMPUTE_DATE_FROM = "2024-03-01";
const PRECOMPUTE_DATE_TO = "2024-05-01";
// El Niño phase of the recorded period — the cooling-driven ramp starts in April.
const EL_NINO_FROM = "2024-04-01";
const PRECOMPUTE_DATE_TO_INCLUSIVE = "2024-04-30";
const PRECOMPUTE_LABEL = "01 Mar 2024 - 30 Apr 2024";
const PREDICTIVE_HORIZON_STEPS = 8;
const PREDICTIVE_TOP_K = 4;
const METRICS: readonly MetricConfig[] = [
  {
    id: "energy",
    label: "Energy Use",
    shortLabel: "Energy",
    unit: " kWh",
    base: "baseline_kwh",
    opt: "optimized_kwh",
    summary: "Energy saved",
    meaning: "Shows total energy reduction from the MPC replay.",
  },
  {
    id: "power",
    label: "Power / Demand",
    shortLabel: "Power",
    unit: " kW",
    base: "peak_baseline_kw",
    opt: "peak_optimized_kw",
    summary: "Demand reduced",
    meaning: "Shows peak shaving and load flattening behavior.",
  },
  {
    id: "temperature",
    label: "Comfort / Indoor Temperature",
    shortLabel: "Comfort",
    unit: " °C",
    base: "baseline_temperature_c",
    opt: "optimized_temperature_c",
    summary: "Temperature change",
    meaning: "Shows whether energy saving trades off against comfort.",
    band: { y1: 23, y2: 26, label: "comfort band" },
  },
  {
    id: "setpoint",
    label: "HVAC Control / Setpoint",
    shortLabel: "Setpoint",
    unit: " °C",
    base: "baseline_setpoint_c",
    opt: "optimized_setpoint_c",
    summary: "Setpoint shift",
    meaning: "Shows the cooling setpoint action selected by MPC.",
  },
  {
    id: "loading",
    label: "Electrical Loading",
    shortLabel: "Loading",
    unit: "%",
    base: "baseline_loading_pct",
    opt: "optimized_loading_pct",
    summary: "Loading reduced",
    meaning: "Shows normalized electrical stress reduction versus the selected range peak.",
    thresholds: [80, 90, 100],
  },
] as const;

const ddmm = (d: string) => {
  const [, m, day] = d.split("-");
  return `${day}/${m}`;
};

const fullDate = (date: string) => new Intl.DateTimeFormat("en-GB", {
  day: "2-digit", month: "short", year: "numeric", timeZone: "UTC",
}).format(new Date(`${date}T00:00:00Z`));

const timeLabel = (value: string) => new Intl.DateTimeFormat("en-GB", {
  day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  timeZone: "Asia/Ho_Chi_Minh",
}).format(new Date(value));

const periodLabel = (range: DateRange | null) => {
  if (!range) return PRECOMPUTE_LABEL;
  if (range.start === range.end) return fullDate(range.start);
  return `${fullDate(range.start)} - ${fullDate(range.end)}`;
};

const nextDay = (date: string) => {
  const [year, month, day] = date.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + 1)).toISOString().slice(0, 10);
};

const clampRange = (start: string, end: string) => {
  const safeStart = start < PRECOMPUTE_DATE_FROM ? PRECOMPUTE_DATE_FROM : start;
  const safeEnd = end > PRECOMPUTE_DATE_TO_INCLUSIVE ? PRECOMPUTE_DATE_TO_INCLUSIVE : end;
  return safeStart <= safeEnd
    ? { start: safeStart, end: safeEnd }
    : { start: safeEnd, end: safeEnd };
};

const chartInterval = (points: number, timestep = false) => {
  if (timestep) {
    if (points <= 24) return 0;
    if (points <= 48) return 2;
    if (points <= 96) return 5;
    return "preserveStartEnd" as const;
  }
  if (points <= 10) return 0;
  if (points <= 21) return 1;
  if (points <= 35) return 2;
  return "preserveStartEnd" as const;
};

const chartMinTickGap = (points: number, timestep = false) => {
  if (timestep) {
    if (points <= 24) return 6;
    if (points <= 48) return 12;
    if (points <= 96) return 16;
    return 30;
  }
  if (points <= 10) return 8;
  if (points <= 21) return 18;
  if (points <= 35) return 28;
  return 36;
};

const numeric = (value: unknown) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const VN_LOCALE = "vi-VN";
const formatNumber = (value: number, maximumFractionDigits = 0, minimumFractionDigits = 0) => (
  value.toLocaleString(VN_LOCALE, { maximumFractionDigits, minimumFractionDigits })
);

const formatPercent = (value: number | null | undefined) => (
  value == null || !Number.isFinite(value)
    ? "."
    : `${formatNumber(value, 2, 2)}%`
);

const formatMinutes = (value: number | null | undefined) => (
  value == null || !Number.isFinite(value)
    ? "."
    : `${formatNumber(Math.round(value))} min`
);

const formatMetricValue = (value: number | null | undefined, unit: string) => {
  if (value == null || !Number.isFinite(value)) return ".";
  const abs = Math.abs(value);
  const digits = unit.includes("°C") ? 1 : abs >= 100 ? 0 : abs >= 10 ? 1 : 2;
  return `${formatNumber(value, digits, unit.includes("°C") ? 1 : 0)}${unit}`;
};

const aggregateMetric = (rows: any[], key: string, metricId: string) => {
  const values = rows.map((row) => numeric(row[key])).filter((v): v is number => v != null);
  if (!values.length) return null;
  if (metricId === "energy") return values.reduce((sum, value) => sum + value, 0);
  if (metricId === "temperature" || metricId === "setpoint") {
    return values.reduce((sum, value) => sum + value, 0) / values.length;
  }
  return Math.max(...values);
};

const metricDomain = (metric: MetricConfig): [number | "auto", number | "auto"] => {
  if (metric.id === "temperature") return [20, 30];
  if (metric.id === "setpoint") return [22, 28];
  if (metric.id === "loading") return [0, 105];
  return [0, "auto"];
};

function MetricHelp({ text }: { text: string }) {
  return (
    <button
      type="button"
      aria-label="Explain metric"
      className="group/help relative inline-flex rounded-full outline-none focus-visible:ring-2 focus-visible:ring-teal/30"
    >
      <Info size={12} className="text-text-muted transition group-hover/help:text-teal" />
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 w-56 -translate-x-1/2 rounded-lg border border-border/70 bg-slate-950 px-2.5 py-2 text-[11px] font-normal leading-snug text-white opacity-0 shadow-lg transition group-hover/help:opacity-100 group-focus-within/help:opacity-100"
      >
        {text}
      </span>
    </button>
  );
}

function MetricReadout({ label, value, sub, tone = "text-text-primary", help, tourId }: {
  label: string; value: string; sub?: string; tone?: string; help: string; tourId?: string;
}) {
  return (
    <div data-tour-id={tourId} className="group/readout rounded-lg px-2 py-1.5 transition hover:bg-white/70">
      <div className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary">
        <span>{label}</span>
        <MetricHelp text={help} />
      </div>
      <p className={`mt-0.5 text-[19px] font-semibold leading-tight tracking-tight tabular-nums ${tone}`}>
        {value}
      </p>
      {sub && <p className="mt-0.5 text-[10.5px] leading-snug text-text-muted">{sub}</p>}
    </div>
  );
}

function MetricComparisonCard({ metric, baseline, optimized, delta, deltaPercent, period, index }: {
  metric: MetricConfig; baseline?: number | null; optimized?: number | null;
  delta?: number | null; deltaPercent?: number | null; period: string; index: number;
}) {
  const positive = (delta ?? 0) >= 0;
  const maxValue = Math.max(Number(baseline) || 0, Number(optimized) || 0, 1);
  const optimizedWidth = `${Math.max(4, Math.min(100, ((Number(optimized) || 0) / maxValue) * 100))}%`;
  const baselineWidth = `${Math.max(4, Math.min(100, ((Number(baseline) || 0) / maxValue) * 100))}%`;
  const deltaText = delta == null ? "." : formatMetricValue(Math.abs(delta), metric.unit);
  const optimizedText = formatMetricValue(optimized, metric.unit);
  const baselineText = formatMetricValue(baseline, metric.unit);
  const deltaPercentText = deltaPercent == null || !Number.isFinite(deltaPercent)
    ? null
    : `${formatPercent(Math.abs(deltaPercent))} ${positive ? "reduction" : "increase"}`;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 26, delay: index * 0.05 }}
      className="rounded-2xl border border-border/65 bg-white px-4 py-3 shadow-[0_18px_45px_-36px_rgba(15,23,42,0.35)]"
    >
      <div className="flex items-start gap-2.5">
        <div className="grid h-8 w-8 shrink-0 place-items-center text-teal">
          <Zap size={23} strokeWidth={1.9} />
        </div>
        <div className="min-w-0">
          <h4 className="text-[17px] font-semibold leading-tight tracking-tight text-text-primary">
            {metric.label} Comparison
          </h4>
          <p className="mt-0.5 text-[12px] text-text-muted">{period}</p>
        </div>
      </div>

      <div className="mt-3 grid gap-4 lg:grid-cols-[1fr_184px]">
        <div className="space-y-3">
          <div>
            <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-[13px] font-semibold text-text-primary">
                <span className="h-2.5 w-2.5 rounded-full bg-teal shadow-[0_0_0_4px_rgba(15,118,110,0.10)]" />
                <span className="tabular-nums text-teal">{optimizedText}</span>
                <span className="text-text-secondary">With AI</span>
                <MetricHelp text={metric.meaning} />
              </div>
              {deltaPercentText && positive && (
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                  {deltaPercentText}
                </span>
              )}
            </div>
            <div className="h-7 overflow-hidden rounded-md bg-emerald-50 shadow-inner">
              <div
                className="h-full rounded-md bg-gradient-to-r from-emerald-700 via-teal to-emerald-400 shadow-[0_8px_18px_-10px_rgba(15,118,110,0.7)] transition-[width] duration-500"
                style={{ width: optimizedWidth }}
              />
            </div>
          </div>

          <div>
            <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-[13px] font-semibold text-text-primary">
                <span className="h-2.5 w-2.5 rounded-full bg-slate-400 shadow-[0_0_0_4px_rgba(148,163,184,0.16)]" />
                <span className="tabular-nums text-slate-700">{baselineText}</span>
                <span className="text-text-secondary">Without AI</span>
                <MetricHelp text={`Baseline ${metric.shortLabel.toLowerCase()} from recorded EnergyPlus telemetry. This is the no-AI reference.`} />
              </div>
            </div>
            <div className="h-7 overflow-hidden rounded-md bg-slate-100 shadow-inner">
              <div
                className="h-full rounded-md bg-gradient-to-r from-slate-300 via-slate-400 to-slate-500 transition-[width] duration-500"
                style={{ width: baselineWidth }}
              />
            </div>
          </div>
        </div>

        <div data-tour-id="validation-delta-card" className="border-t border-border/70 pt-4 lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0">
          <div className="flex items-center gap-1.5 text-[12px] font-medium text-text-primary">
            <span>{metric.summary}</span>
            <MetricHelp text={metric.meaning} />
          </div>
          <div data-tour-id="validation-energy-saved-value">
            <p className={`mt-1.5 text-[34px] font-bold leading-none tracking-tight tabular-nums ${
              positive ? "text-success" : "text-amber-700"
            }`}>
              {deltaText.replace(metric.unit, "")}
            </p>
            <p className="mt-1 text-[14px] font-medium text-text-muted">{metric.unit.trim()}</p>
          </div>
          {deltaPercentText && <p className="mt-2 text-[11px] font-semibold text-emerald-700">{deltaPercentText}</p>}
        </div>
      </div>
    </motion.div>
  );
}

function ImpactCard({ costSaving, co2Avoided, aiAddedComfort, baselineComfort, days, period, index }: {
  costSaving?: number; co2Avoided?: number; aiAddedComfort?: number; baselineComfort?: number;
  days?: number; period: string; index: number;
}) {
  const comfortTone = (aiAddedComfort ?? 0) > 0 ? "text-amber-700" : "text-success";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 26, delay: index * 0.05 }}
      className="rounded-2xl border border-border/65 bg-white px-4 py-3 shadow-[0_18px_45px_-36px_rgba(15,23,42,0.35)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5">
          <div className="grid h-8 w-8 shrink-0 place-items-center text-teal">
            <BarChart3 size={22} strokeWidth={1.9} />
          </div>
          <div>
            <h4 className="text-[17px] font-semibold leading-tight tracking-tight text-text-primary">Operational Impact</h4>
            <p className="mt-0.5 text-[12px] text-text-muted">{days ?? "."} recorded day{days === 1 ? "" : "s"}</p>
          </div>
        </div>
        <p className="rounded-full border border-border/70 px-2.5 py-1 text-[11px] font-medium text-text-secondary">
          Same period
        </p>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="grid justify-items-center text-center">
          <MetricReadout
            label="Cost saved"
            value={costSaving != null ? fmtVnd(Math.round(costSaving)) : "."}
            sub={period}
            tone={costSaving != null && costSaving < 0 ? "text-amber-700" : "text-success"}
            help="Estimated electricity cost impact over the selected period."
          />
        </div>
        <div data-tour-id="validation-co2" className="grid justify-items-center border-t border-border/70 pt-3 text-center sm:border-l sm:border-t-0 sm:pl-3 sm:pt-0">
          <MetricReadout
            label="CO2 avoided"
            value={co2Avoided != null ? `${formatNumber(Math.round(co2Avoided))} kg` : "."}
            tone={co2Avoided != null && co2Avoided < 0 ? "text-amber-700" : "text-blue-600"}
            help="Estimated emissions impact derived from saved energy."
            tourId="validation-co2-value"
          />
        </div>
      </div>

      <div className="mt-3 rounded-xl border border-border/55 bg-surface-muted/45 px-3 py-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-1.5 text-[12px] font-medium text-text-secondary">
            <span>AI-added comfort violation</span>
            <MetricHelp text="Additional comfort-violation minutes caused by the MPC branch. Zero means AI did not make comfort worse than baseline." />
          </div>
          <p className={`text-[14px] font-semibold tabular-nums ${comfortTone}`}>{formatMinutes(aiAddedComfort ?? 0)}</p>
        </div>
        <p className="mt-1 text-[11px] text-text-muted">
          Baseline violation: <span className="font-semibold text-red-600">{formatMinutes(baselineComfort)}</span>
        </p>
      </div>
    </motion.div>
  );
}

function MetricTooltip({ active, payload, label, metric, isTimestep }: {
  active?: boolean; payload?: any[]; label?: string; metric: MetricConfig; isTimestep: boolean;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload || {};
  const baseline = numeric(row[metric.base]);
  const optimized = numeric(row[metric.opt]);
  const delta = baseline != null && optimized != null ? baseline - optimized : null;
  const pct = delta != null && baseline ? (delta / baseline) * 100 : null;
  const positive = (delta ?? 0) >= 0;

  return (
    <div className="min-w-[220px] rounded-xl border border-border/70 bg-white px-3 py-2 text-[12px] shadow-lg">
      <p className="font-semibold text-text-primary">
        {isTimestep ? timeLabel(String(label)) : fullDate(String(label))}
      </p>
      <div className="mt-2 space-y-1 tabular-nums">
        <div className="flex items-center justify-between gap-4">
          <span className="text-text-muted">Without AI</span>
          <span className="font-medium text-slate-700">{formatMetricValue(baseline, metric.unit)}</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-text-muted">With AI</span>
          <span className="font-medium text-teal">{formatMetricValue(optimized, metric.unit)}</span>
        </div>
        <div className="flex items-center justify-between gap-4 border-t border-border/60 pt-1">
          <span className="text-text-muted">Delta</span>
          <span className={`font-semibold ${positive ? "text-success" : "text-amber-700"}`}>
            {delta == null ? "." : formatMetricValue(delta, metric.unit)}
            {pct != null ? ` (${formatPercent(pct)})` : ""}
          </span>
        </div>
      </div>
      <p className="mt-2 max-w-[260px] text-[11px] leading-snug text-text-muted">{metric.meaning}</p>
    </div>
  );
}

export default function CampaignWhatIf() {
  const [metricId, setMetricId] = useState<string>("energy");
  const [dateFrom, setDateFrom] = useState(PRECOMPUTE_DATE_FROM);
  const [dateTo, setDateTo] = useState(PRECOMPUTE_DATE_TO_INCLUSIVE);
  const [data, setData] = useState<WhatIfData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showElNino, setShowElNino] = useState(true);

  // Tutorial Mode can drive the metric + El-Niño overlay from its step actions.
  const tutorialMetric = useTutorialStore((s) => s.validationMetric);
  const tutorialElNino = useTutorialStore((s) => s.elNinoOverride);
  useEffect(() => { if (tutorialMetric) setMetricId(tutorialMetric); }, [tutorialMetric]);
  useEffect(() => { if (tutorialElNino !== null) setShowElNino(tutorialElNino); }, [tutorialElNino]);

  const run = useCallback(() => {
    const selected = clampRange(dateFrom, dateTo);
    setLoading(true);
    setError(null);
    api.whatifCache({
      mode: "predictive_replay",
      date_from: selected.start,
      date_to: nextDay(selected.end),
      horizon_steps: PREDICTIVE_HORIZON_STEPS,
      top_k: PREDICTIVE_TOP_K,
      resolution: "auto",
    })
      .then(setData)
      .catch(() => {
        setData(null);
        setError(`Precomputed predictive replay cache is unavailable for ${PRECOMPUTE_LABEL}. Run scripts/precompute_predictive_whatif.py for this range.`);
      })
      .finally(() => setLoading(false));
  }, [dateFrom, dateTo]);

  useEffect(() => { run(); }, [run]);

  const k = data?.kpi;
  const isTimestep = data?.metadata?.resolution === "timestep";
  const metric = METRICS.find((m) => m.id === metricId) ?? METRICS[0];
  const chartData = isTimestep && data?.series?.length ? data.series : data?.daily ?? [];
  const xKey = isTimestep ? "timestamp" : "date";
  const visibleRange = data?.daily?.length ? {
    start: data.daily[0].date,
    end: data.daily[data.daily.length - 1].date,
  } : null;
  const visiblePeriod = periodLabel(visibleRange);
  const recordedThrough = visibleRange ? fullDate(visibleRange.end) : PRECOMPUTE_LABEL;
  const pointCount = chartData.length;
  // El Niño overlay band: first chart point on/after 1 Apr -> end of the range.
  const elNinoBand = useMemo(() => {
    const rows = chartData as any[];
    if (!rows.length) return null;
    const from = Date.parse(`${EL_NINO_FROM}T00:00:00+07:00`);
    const at = (row: any) => {
      const raw = isTimestep ? row.timestamp : row.date;
      return isTimestep ? Date.parse(raw) : Date.parse(`${raw}T00:00:00+07:00`);
    };
    const startIdx = rows.findIndex((row) => at(row) >= from);
    if (startIdx < 0) return null;
    return { x1: rows[startIdx][xKey], x2: rows[rows.length - 1][xKey] };
  }, [chartData, isTimestep, xKey]);
  const cardBaseline = metric.id === "energy" ? k?.baseline_kwh : aggregateMetric(chartData, metric.base, metric.id);
  const cardOptimized = metric.id === "energy" ? k?.optimized_kwh : aggregateMetric(chartData, metric.opt, metric.id);
  const cardDelta = cardBaseline != null && cardOptimized != null ? cardBaseline - cardOptimized : null;
  const cardDeltaPercent = cardDelta != null && cardBaseline ? (cardDelta / cardBaseline) * 100 : null;
  const setRange = (start: string, end: string) => {
    const selected = clampRange(start, end);
    setDateFrom(selected.start);
    setDateTo(selected.end);
  };

  return (
    <div className="card-elevated px-5 py-4">
      {loading && (
        <div className="mb-2 flex items-center gap-2 text-[11px] font-medium text-text-muted">
          <Loader2 size={13} className="animate-spin text-teal" />
          Loading validation data
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2.5 rounded-xl border border-border/60 bg-surface-muted/35 px-3 py-2.5">
        <CalendarDays size={15} className="text-teal" />
        <div>
          <p className="text-[10.5px] font-medium uppercase tracking-wide text-text-muted">Recorded period</p>
          <p className="text-[12px] font-semibold text-text-primary">{visiblePeriod}</p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
          <label className="flex items-center gap-1.5">
            From
            <input type="date" value={dateFrom} min={PRECOMPUTE_DATE_FROM}
                   max={dateTo}
                   onChange={(event) => setRange(event.target.value, dateTo)}
                   className="rounded-lg border border-border bg-surface px-2 py-1.5 text-[12px] font-medium text-text-primary outline-none focus:border-teal" />
          </label>
          <label className="flex items-center gap-1.5">
            To
            <input type="date" value={dateTo} min={dateFrom}
                   max={PRECOMPUTE_DATE_TO_INCLUSIVE}
                   onChange={(event) => setRange(dateFrom, event.target.value)}
                   className="rounded-lg border border-border bg-surface px-2 py-1.5 text-[12px] font-medium text-text-primary outline-none focus:border-teal" />
          </label>
        </div>
      </div>

      {error ? (
        <div className="mt-4 grid h-[120px] place-items-center text-[12px] text-text-muted">
          {error}
        </div>
      ) : (
        <>
          <div data-tour-id="validation-summary-cards" className="mt-3 grid items-stretch gap-2.5 xl:grid-cols-[1.45fr_1fr]">
            <MetricComparisonCard
              index={0}
              metric={metric}
              baseline={cardBaseline}
              optimized={cardOptimized}
              delta={cardDelta}
              deltaPercent={cardDeltaPercent}
              period={visiblePeriod}
            />
            <ImpactCard
              index={1}
              costSaving={k?.cost_saving_vnd}
              co2Avoided={k?.co2_avoided_kg}
              aiAddedComfort={k?.ai_added_comfort_violation_min ?? 0}
              baselineComfort={k?.baseline_comfort_violation_min}
              days={k?.days}
              period={recordedThrough ? `through ${recordedThrough}` : visiblePeriod}
            />
          </div>

          <div className="mt-4 rounded-2xl border border-border/60 bg-surface-muted/30 px-3 py-2.5">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-muted">Metric view</span>
                <MetricHelp text="Choose which baseline-vs-AI time-series metric to inspect. The visual style stays consistent across metrics." />
              </div>
              <div data-tour-id="validation-metric-controls" className="flex flex-wrap items-center gap-2">
              <select
                data-tour-id="validation-metric-selector"
                value={metricId}
                onChange={(event) => setMetricId(event.target.value)}
                className="min-w-[250px] rounded-lg border border-teal/30 bg-white px-3 py-2 text-[13px] font-semibold text-text-primary shadow-sm outline-none transition focus:border-teal focus:ring-2 focus:ring-teal/15"
              >
                {METRICS.map((m) => (
                  <option key={m.id} value={m.id}>{m.label}</option>
                ))}
              </select>
              <label data-tour-id="validation-el-nino-toggle" className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-amber-300/70 bg-amber-50/70 px-2.5 py-2 text-[12px] font-medium text-amber-800 transition hover:bg-amber-50">
                <input type="checkbox" checked={showElNino}
                       onChange={(event) => setShowElNino(event.target.checked)}
                       className="h-3.5 w-3.5 accent-amber-500" />
                <Sun size={13} className="text-amber-500" />
                El Niño
                <MetricHelp text="Shade the chart background over the El Niño phase of the recorded period (from 1 Apr 2024 onward), when cooling-driven demand ramps up." />
              </label>
              </div>
              <div className="ml-auto flex items-center gap-3 text-[11px] text-text-muted">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-3 rounded-sm" style={{ background: "#94A3B8" }} /> Without AI
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-3 rounded-sm" style={{ background: "#0F766E" }} /> With AI
                </span>
              </div>
            </div>
          </div>
          <div data-tour-id="validation-timeseries-chart" className="mt-2 h-[260px]">
            {chartData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 6, right: 10, bottom: 0, left: 8 }}>
                  <defs>
                    <linearGradient id="cwTeal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0F766E" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="#0F766E" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#EEF2F7" vertical={false} />
                  {showElNino && elNinoBand && (
                    <ReferenceArea x1={elNinoBand.x1} x2={elNinoBand.x2}
                                   fill="#f59e0b" fillOpacity={0.08} stroke="#fcd34d" strokeOpacity={0.5}
                                   label={{ value: "El Niño", fill: "#b45309", fontSize: 10, position: "insideTopRight" }} />
                  )}
                  <XAxis dataKey={xKey}
                         tickFormatter={isTimestep ? timeLabel : ddmm}
                         tick={{ fontSize: 10, fill: "#94A3B8" }}
                         interval={chartInterval(pointCount, isTimestep)}
                         minTickGap={chartMinTickGap(pointCount, isTimestep)}
                         tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false}
                         domain={metricDomain(metric)} width={76}
                         tickFormatter={(value: number) => `${formatNumber(Math.round(value))}${metric.unit}`} />
                  {metric.band && (
                    <ReferenceArea y1={metric.band.y1} y2={metric.band.y2}
                                   fill="#14b8a6" fillOpacity={0.08}
                                   label={{ value: metric.band.label, fill: "#0F766E", fontSize: 10 }} />
                  )}
                  {metric.thresholds?.map((value) => (
                    <ReferenceLine key={value} y={value} stroke={value >= 100 ? "#ef4444" : "#f59e0b"}
                                   strokeDasharray="3 3"
                                   label={{ value: `${value}%`, fill: value >= 100 ? "#ef4444" : "#b45309", fontSize: 10 }} />
                  ))}
                  {metric.id === "power" && cardBaseline != null && (
                    <ReferenceLine y={cardBaseline} stroke="#64748B" strokeDasharray="3 3"
                                   label={{ value: "baseline peak", fill: "#64748B", fontSize: 10 }} />
                  )}
                  <Tooltip content={(props) => (
                    <MetricTooltip {...props} metric={metric} isTimestep={isTimestep} />
                  )} />
                  <Area type="monotone" dataKey={metric.opt} stroke="#0F766E" strokeWidth={2}
                        fill="url(#cwTeal)" dot={false} />
                  <Line type="monotone" dataKey={metric.base} stroke="#94A3B8" strokeWidth={1.6}
                        strokeDasharray="4 3" dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <div className="grid h-full place-items-center text-[12px] text-text-muted">
                {loading ? "Loading precomputed predictive replay cache..." : "No data."}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
