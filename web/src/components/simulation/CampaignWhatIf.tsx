"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { CalendarDays, Loader2, Sparkles, TrendingDown, Wind } from "lucide-react";
import { motion } from "motion/react";
import { api } from "@/lib/api";
import { fmtVnd } from "@/lib/format";

type Campaign = Awaited<ReturnType<typeof api.campaign>>;
type RangeMode = "period" | "month" | "custom";
type DateRange = { start: string; end: string };

const DELTAS = [1, 2, 3] as const;            // tree surrogate steps cleanly on integer °C
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

/** One KPI tile in the campaign hero. */
function Stat({ label, value, sub, tone = "#0F766E", index }: {
  label: string; value: string; sub?: string; tone?: string; index: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 26, delay: index * 0.05 }}
      className="rounded-xl border border-border/55 bg-surface px-3.5 py-3"
    >
      <p className="text-[11.5px] font-medium text-text-secondary">{label}</p>
      <p className="mt-0.5 text-[21px] font-semibold leading-tight tracking-tight tabular-nums"
         style={{ color: tone }}>{value}</p>
      {sub && <p className="text-[10.5px] text-text-muted">{sub}</p>}
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
  const [delta, setDelta] = useState<number>(1);
  const [metricId, setMetricId] = useState<string>("energy");
  const [rangeMode, setRangeMode] = useState<RangeMode>("period");
  const [month, setMonth] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [datasetRange, setDatasetRange] = useState<DateRange | null>(null);
  const [data, setData] = useState<Campaign | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const query = useMemo(() => {
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

  const run = useCallback(() => {
    setLoading(true); setError(false);
    api.campaign(query)
      .then((result) => {
        setData(result);
        if (rangeMode === "period" && result.daily.length) {
          setDatasetRange({
            start: result.daily[0].date,
            end: result.daily[result.daily.length - 1].date,
          });
        }
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [query, rangeMode]);

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
        <div className="ml-auto flex items-center gap-2">
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
      </div>

      <p className="mt-1 text-[11.5px] text-text-muted">
        {data
          ? `Raise cooling setpoint +${data.policy.setpoint_delta_c}°C during ${data.policy.peak_window} on weekdays, rolled across ${k?.days} days. Baseline = measured; with-AI via the ${data.policy.engine}.`
          : "Rolling a fixed AI setpoint policy across the whole period."}
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
          Campaign model unavailable on this dataset.
        </div>
      ) : (
        <>
          {/* KPI hero */}
          <div className="mt-3 grid grid-cols-2 gap-2.5 md:grid-cols-4 xl:grid-cols-5">
            <Stat index={0} label="Energy saved" tone="#16A34A"
                  value={k ? `${Math.round(k.saving_kwh).toLocaleString()} kWh` : "·"}
                  sub={k ? `-${k.saving_percent}% vs no AI · ${visiblePeriod}` : undefined} />
            <Stat index={1} label="Cost saved" tone="#16A34A"
                  value={k ? fmtVnd(Math.round(k.cost_saving_vnd)) : "·"}
                  sub={k ? visiblePeriod : undefined} />
            <Stat index={2} label="Without AI"
                  value={k ? `${Math.round(k.baseline_kwh).toLocaleString()} kWh` : "·"}
                  sub={k ? `${k.days} recorded day${k.days === 1 ? "" : "s"} · through ${recordedThrough}` : undefined}
                  tone="#334155" />
            <Stat index={3} label="With AI"
                  value={k ? `${Math.round(k.optimized_kwh).toLocaleString()} kWh` : "·"}
                  sub={k ? visiblePeriod : undefined} tone="#0F766E" />
            <Stat index={4} label="CO2 avoided" tone="#2563EB"
                  value={k ? `${Math.round(k.co2_avoided_kg).toLocaleString()} kg` : "·"}
                  sub={k ? `comfort +${Math.round(k.comfort_violation_delta_min)} min · through ${recordedThrough}` : undefined} />
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
                {loading ? "Running campaign across the period…" : "No data."}
              </div>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-[11px] text-text-muted">
            <span className="inline-flex items-center gap-1.5">
              <TrendingDown size={12} className="text-success" />
              The teal band is the building running under the AI policy; the gap to the dashed line is the saving.
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Wind size={12} /> Same weather and occupancy; only the setpoint policy differs.
            </span>
          </div>
        </>
      )}
    </div>
  );
}
