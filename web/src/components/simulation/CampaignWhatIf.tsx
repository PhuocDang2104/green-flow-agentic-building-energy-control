"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { CalendarDays, Info, Loader2, Sparkles, TrendingDown, Wind } from "lucide-react";
import { motion } from "motion/react";
import { api } from "@/lib/api";
import { fmtVnd } from "@/lib/format";

type WhatIfData = Awaited<ReturnType<typeof api.campaign>> | Awaited<ReturnType<typeof api.whatifCache>>;
type RangeMode = "period" | "month" | "custom";
type AnalysisMode = "campaign" | "predictive";
type DateRange = { start: string; end: string };

const DELTAS = [1, 2, 3] as const;            // tree surrogate steps cleanly on integer °C
const PREDICTIVE_HORIZON_STEPS = 8;
const PREDICTIVE_TOP_K = 4;
const METRICS = [
  { id: "energy", label: "Daily energy", unit: " kWh", base: "baseline_kwh", opt: "optimized_kwh" },
  { id: "peak", label: "Daily peak", unit: " kW", base: "peak_baseline_kw", opt: "peak_optimized_kw" },
] as const;

const ddmm = (d: string) => {
  const [, m, day] = d.split("-");
  return `${day}/${m}`;
};

const fullDate = (date: string) => new Intl.DateTimeFormat("en-GB", {
  day: "2-digit", month: "short", year: "numeric", timeZone: "UTC",
}).format(new Date(`${date}T00:00:00Z`));

const periodLabel = (range: DateRange | null) => {
  if (!range) return "Loading recorded period";
  if (range.start === range.end) return fullDate(range.start);
  return `${fullDate(range.start)} - ${fullDate(range.end)}`;
};

const nextDay = (date: string) => {
  const [year, month, day] = date.split("-").map(Number);
  const value = new Date(Date.UTC(year, month - 1, day + 1));
  return value.toISOString().slice(0, 10);
};

const nextMonth = (monthValue: string) => {
  const [year, month] = monthValue.split("-").map(Number);
  return new Date(Date.UTC(year, month, 1)).toISOString().slice(0, 10);
};

const apiDate = (date: string) => `${date}T00:00:00+07:00`;

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

function MetricReadout({ label, value, sub, tone = "text-text-primary", help }: {
  label: string; value: string; sub?: string; tone?: string; help: string;
}) {
  return (
    <div className="group/readout rounded-lg px-2 py-1.5 transition hover:bg-white/70">
      <div className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary">
        <span>{label}</span>
        <MetricHelp text={help} />
      </div>
      <p className={`mt-0.5 text-[21px] font-semibold leading-tight tracking-tight tabular-nums ${tone}`}>
        {value}
      </p>
      {sub && <p className="mt-0.5 text-[10.5px] leading-snug text-text-muted">{sub}</p>}
    </div>
  );
}

function EnergyComparisonCard({ baseline, optimized, savingPercent, period, index }: {
  baseline?: number; optimized?: number; savingPercent?: number; period: string; index: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 26, delay: index * 0.05 }}
      className="rounded-2xl border border-emerald-900/10 bg-gradient-to-br from-emerald-50/70 via-white to-white px-4 py-3.5 shadow-[0_18px_40px_-30px_rgba(15,118,110,0.55)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-700/80">Energy use comparison</p>
          <p className="mt-1 text-[12px] text-text-muted">{period}</p>
        </div>
        <div className="rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 tabular-nums">
          -{savingPercent ?? "·"}% vs no AI
        </div>
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <MetricReadout
          label="Without AI"
          value={baseline != null ? `${Math.round(baseline).toLocaleString()} kWh` : "·"}
          tone="text-slate-700"
          help="Baseline consumption from recorded data. This is the no-AI reference used for comparison."
        />
        <MetricReadout
          label="With AI"
          value={optimized != null ? `${Math.round(optimized).toLocaleString()} kWh` : "·"}
          tone="text-teal"
          help="Estimated consumption after applying the selected AI setpoint policy to the same days."
        />
      </div>
    </motion.div>
  );
}

function ImpactCard({ energySaved, costSaving, co2Avoided, comfortDelta, days, period, index }: {
  energySaved?: number; costSaving?: number; co2Avoided?: number; comfortDelta?: number; days?: number; period: string; index: number;
}) {
  const comfortTone = (comfortDelta ?? 0) > 0 ? "text-amber-700" : "text-success";
  const comfortLabel = `${comfortDelta != null && comfortDelta > 0 ? "+" : ""}${Math.round(comfortDelta ?? 0).toLocaleString()} min`;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 26, delay: index * 0.05 }}
      className="rounded-2xl border border-border/55 bg-surface px-4 py-3.5"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text-muted">Operational impact</p>
          <p className="mt-1 text-[12px] text-text-muted">{days ?? "·"} recorded day{days === 1 ? "" : "s"}</p>
        </div>
        <p className="rounded-full border border-border/70 px-2.5 py-1 text-[11px] font-medium text-text-secondary">
          same period
        </p>
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
        <MetricReadout
          label="Energy saved"
          value={energySaved != null ? `${Math.round(energySaved).toLocaleString()} kWh` : "·"}
          tone="text-success"
          help="Difference between Without AI and With AI. Positive value means lower energy use with AI."
        />
        <MetricReadout
          label="Cost saved"
          value={costSaving != null ? fmtVnd(Math.round(costSaving)) : "·"}
          sub={period}
          tone="text-success"
          help="Estimated electricity cost reduction from the energy saved over the selected period."
        />
        <MetricReadout
          label="CO₂ avoided"
          value={co2Avoided != null ? `${Math.round(co2Avoided).toLocaleString()} kg` : "·"}
          tone="text-blue-600"
          help="Estimated emissions avoided by consuming less electricity. This is derived from saved energy."
        />
      </div>

      <div className="mt-3 rounded-xl border border-border/55 bg-surface-muted/45 px-3 py-2">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary">
            <span>Comfort change</span>
            <MetricHelp text="Change in comfort-violation minutes after applying the AI policy. Positive values mean more minutes outside the comfort rule, so savings should be weighed against occupant comfort." />
          </div>
          <p className={`text-[13px] font-semibold tabular-nums ${comfortTone}`}>{comfortLabel}</p>
        </div>
      </div>
    </motion.div>
  );
}

/**
 * Period (campaign) what-if: the building run over the WHOLE dataset WITHOUT any
 * AI vs WITH a fixed setpoint policy. baseline = measured; with-AI = measured
 * minus the structural surrogate's reduction. Shows the aggregate impact a
 * decision-maker actually cares about, not a single day.
 */
export default function CampaignWhatIf() {
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("campaign");
  const [delta, setDelta] = useState<number>(1);
  const [metricId, setMetricId] = useState<string>("energy");
  const [rangeMode, setRangeMode] = useState<RangeMode>("period");
  const [month, setMonth] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [datasetRange, setDatasetRange] = useState<DateRange | null>(null);
  const [data, setData] = useState<WhatIfData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const campaignQuery = useMemo(() => {
    const payload: Parameters<typeof api.campaign>[0] = { setpoint_delta: delta };
    if (rangeMode === "month" && month) {
      payload.date_from = apiDate(`${month}-01`);
      payload.date_to = apiDate(nextMonth(month));
    }
    if (rangeMode === "custom" && dateFrom && dateTo && dateFrom <= dateTo) {
      payload.date_from = apiDate(dateFrom);
      payload.date_to = apiDate(nextDay(dateTo));
    }
    return payload;
  }, [dateFrom, dateTo, delta, month, rangeMode]);

  const cacheQuery = useMemo(() => {
    const payload: Parameters<typeof api.whatifCache>[0] = {
      mode: "predictive_replay",
      horizon_steps: PREDICTIVE_HORIZON_STEPS,
      top_k: PREDICTIVE_TOP_K,
    };
    if (rangeMode === "period" && datasetRange) {
      payload.date_from = datasetRange.start;
      payload.date_to = nextDay(datasetRange.end);
    }
    if (rangeMode === "month" && month) {
      payload.date_from = `${month}-01`;
      payload.date_to = nextMonth(month);
    }
    if (rangeMode === "custom" && dateFrom && dateTo && dateFrom <= dateTo) {
      payload.date_from = dateFrom;
      payload.date_to = nextDay(dateTo);
    }
    return payload;
  }, [datasetRange, dateFrom, dateTo, month, rangeMode]);

  const run = useCallback(() => {
    setLoading(true); setError(null);
    const request = analysisMode === "campaign"
      ? api.campaign(campaignQuery)
      : api.whatifCache(cacheQuery);
    request
      .then((result) => {
        setData(result);
        if (result.daily.length) {
          setDatasetRange({
            start: result.daily[0].date,
            end: result.daily[result.daily.length - 1].date,
          });
        }
      })
      .catch(() => {
        setData(null);
        setError(analysisMode === "predictive"
          ? "Predictive replay cache is not available for this range. Run the cloud precompute job first."
          : "Campaign model unavailable on this dataset.");
      })
      .finally(() => setLoading(false));
  }, [analysisMode, cacheQuery, campaignQuery]);

  useEffect(() => { run(); }, [run]);

  const k = data?.kpi;
  const metric = METRICS.find((m) => m.id === metricId)!;
  const visibleRange = data?.daily?.length ? {
    start: data.daily[0].date,
    end: data.daily[data.daily.length - 1].date,
  } : null;
  const visiblePeriod = periodLabel(visibleRange);
  const recordedThrough = visibleRange ? fullDate(visibleRange.end) : undefined;

  const changeRangeMode = (mode: RangeMode) => {
    setRangeMode(mode);
    if (mode === "month" && !month && datasetRange) {
      setMonth(datasetRange.start.slice(0, 7));
    }
    if (mode === "custom" && datasetRange) {
      if (!dateFrom) setDateFrom(datasetRange.start);
      if (!dateTo) setDateTo(datasetRange.end);
    }
  };

  return (
    <div className="card-elevated px-5 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <Sparkles size={16} className="text-teal" />
        <h3 className="text-sm font-semibold tracking-tight">Period what-if &middot; building with AI vs without AI</h3>
        {loading && <Loader2 size={13} className="animate-spin text-text-muted" />}
        <div className="ml-auto flex rounded-lg border border-border p-0.5 text-[12px]">
          {([
            ["campaign", "Campaign policy"],
            ["predictive", "Predictive MPC replay"],
          ] as const).map(([mode, label]) => (
            <button key={mode} type="button" onClick={() => setAnalysisMode(mode)}
                    className={`rounded-md px-2.5 py-0.5 font-medium transition ${
                      analysisMode === mode ? "bg-teal text-white" : "text-text-secondary hover:bg-surface-muted"
                    }`}>
              {label}
            </button>
          ))}
        </div>
        <div className={`${analysisMode === "campaign" ? "flex" : "hidden"} items-center gap-2`}>
          <span className="text-[11.5px] text-text-secondary">AI policy: setpoint</span>
          <div className="flex rounded-lg border border-border p-0.5 text-[12px]">
            {DELTAS.map((d) => (
              <button key={d} onClick={() => setDelta(d)}
                      className={`rounded-md px-2.5 py-0.5 font-medium tabular-nums transition ${
                        delta === d ? "bg-teal text-white" : "text-text-secondary hover:bg-surface-muted"}`}>
                +{d}&deg;C
              </button>
            ))}
          </div>
        </div>
        {analysisMode === "predictive" && (
          <div className="rounded-full border border-teal/20 bg-teal-soft px-2.5 py-1 text-[11.5px] font-medium text-teal">
            Precomputed MPC · horizon {PREDICTIVE_HORIZON_STEPS} steps · top {PREDICTIVE_TOP_K}
          </div>
        )}
      </div>

      <p className="mt-1 text-[11.5px] text-text-muted">
        {analysisMode === "campaign" && data
          ? `Raise cooling setpoint +${data.policy.setpoint_delta_c}°C during ${data.policy.peak_window} on weekdays, rolled across ${k?.days} days. Baseline = measured; with-AI via the ${data.policy.engine}.`
          : analysisMode === "campaign"
            ? "Rolling a fixed AI setpoint policy across the whole period."
            : data
              ? `Reading precomputed receding-horizon replay across ${k?.days} days. Baseline = E+ telemetry; with-AI = surrogate MPC branch.`
              : "Reading precomputed predictive replay cache. Heavy MPC replay is not run in the browser request."}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2.5 rounded-xl border border-border/60 bg-surface-muted/35 px-3 py-2.5">
        <CalendarDays size={15} className="text-teal" />
        <div className="mr-2">
          <p className="text-[10.5px] font-medium uppercase tracking-wide text-text-muted">Recorded period</p>
          <p className="text-[12px] font-semibold text-text-primary">{visiblePeriod}</p>
        </div>

        <div className="ml-auto flex rounded-lg border border-border bg-surface p-0.5 text-[11.5px]">
          {([
            ["period", "Full period"], ["month", "Month"], ["custom", "Date range"],
          ] as const).map(([mode, label]) => (
            <button key={mode} type="button" onClick={() => changeRangeMode(mode)}
                    disabled={mode !== "period" && !datasetRange}
                    className={`whitespace-nowrap rounded-md px-2.5 py-1 font-medium transition disabled:opacity-40 ${
                      rangeMode === mode ? "bg-teal text-white" : "text-text-secondary hover:bg-surface-muted"
                    }`}>
              {label}
            </button>
          ))}
        </div>

        {rangeMode === "month" && (
          <label className="flex items-center gap-2 text-[11px] text-text-muted">
            View month
            <input type="month" value={month}
                   min={datasetRange?.start.slice(0, 7)} max={datasetRange?.end.slice(0, 7)}
                   onChange={(event) => setMonth(event.target.value)}
                   className="rounded-lg border border-border bg-surface px-2.5 py-1.5 text-[12px] font-medium text-text-primary outline-none focus:border-teal" />
          </label>
        )}

        {rangeMode === "custom" && (
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
            <label className="flex items-center gap-1.5">
              From
              <input type="date" value={dateFrom} min={datasetRange?.start}
                     max={dateTo || datasetRange?.end}
                     onChange={(event) => {
                       const value = event.target.value;
                       setDateFrom(value);
                       if (dateTo && value > dateTo) setDateTo(value);
                     }}
                     className="rounded-lg border border-border bg-surface px-2 py-1.5 text-[12px] font-medium text-text-primary outline-none focus:border-teal" />
            </label>
            <label className="flex items-center gap-1.5">
              To
              <input type="date" value={dateTo} min={dateFrom || datasetRange?.start}
                     max={datasetRange?.end}
                     onChange={(event) => setDateTo(event.target.value)}
                     className="rounded-lg border border-border bg-surface px-2 py-1.5 text-[12px] font-medium text-text-primary outline-none focus:border-teal" />
            </label>
          </div>
        )}
      </div>

      {error ? (
        <div className="mt-4 grid h-[120px] place-items-center text-[12px] text-text-muted">
          {error}
        </div>
      ) : (
        <>
          {/* KPI hero */}
          <div className="mt-3 grid gap-3 xl:grid-cols-[1.45fr_1fr]">
            <EnergyComparisonCard
              index={0}
              baseline={k?.baseline_kwh}
              optimized={k?.optimized_kwh}
              savingPercent={k?.saving_percent}
              period={visiblePeriod}
            />
            <ImpactCard
              index={1}
              energySaved={k?.saving_kwh}
              costSaving={k?.cost_saving_vnd}
              co2Avoided={k?.co2_avoided_kg}
              comfortDelta={k?.comfort_violation_delta_min}
              days={k?.days}
              period={recordedThrough ? `through ${recordedThrough}` : visiblePeriod}
            />
          </div>

          {/* daily A/B chart */}
          <div className="mt-4 flex items-center gap-2">
            <div className="flex rounded-lg border border-border p-0.5 text-[11.5px]">
              {METRICS.map((m) => (
                <button key={m.id} onClick={() => setMetricId(m.id)}
                        className={`rounded-md px-2 py-0.5 font-medium transition ${
                          metricId === m.id ? "bg-teal text-white" : "text-text-secondary hover:bg-surface-muted"}`}>
                  {m.label}
                </button>
              ))}
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
          <div className="mt-2 h-[260px]">
            {data?.daily?.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={data.daily} margin={{ top: 6, right: 10, bottom: 0, left: 8 }}>
                  <defs>
                    <linearGradient id="cwTeal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0F766E" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="#0F766E" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#EEF2F7" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={ddmm} tick={{ fontSize: 10, fill: "#94A3B8" }}
                         interval="preserveStartEnd" minTickGap={36} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} tickLine={false} axisLine={false}
                         domain={[0, "auto"]} width={76}
                         tickFormatter={(value: number) => `${Math.round(value).toLocaleString()}${metric.unit}`} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #E2E8F0", fontSize: 12 }}
                           labelFormatter={(label: string) => fullDate(label)}
                           formatter={(v: any, n: any) => [`${Number(v).toFixed(1)}${metric.unit}`,
                             n === metric.opt ? "With AI" : "Without AI"]} />
                  <Area type="monotone" dataKey={metric.opt} stroke="#0F766E" strokeWidth={2}
                        fill="url(#cwTeal)" dot={false} />
                  <Line type="monotone" dataKey={metric.base} stroke="#94A3B8" strokeWidth={1.6}
                        strokeDasharray="4 3" dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <div className="grid h-full place-items-center text-[12px] text-text-muted">
                {loading
                  ? analysisMode === "campaign"
                    ? "Running campaign across the period…"
                    : "Loading precomputed predictive replay cache…"
                  : "No data."}
              </div>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px] text-text-muted">
            <span className="inline-flex items-center gap-1.5">
              <TrendingDown size={12} className="text-success" />
              {analysisMode === "campaign"
                ? "The teal band is the building running under the AI policy; the gap to the dashed line is the saving."
                : "The teal band is the precomputed MPC replay; the gap to the dashed line is the predicted control impact."}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Wind size={12} /> {analysisMode === "campaign"
                ? "Same weather and occupancy; only the setpoint policy differs."
                : "The page reads materialized cache; run the cloud precompute job to refresh long ranges."}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
