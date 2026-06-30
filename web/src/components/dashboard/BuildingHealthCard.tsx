import {
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Bell,
  CircleHelp,
  Cloud,
  Clock,
  Leaf,
  Thermometer,
  Waves,
  Wrench,
  Zap,
} from "lucide-react";
import Skeleton from "@/components/shared/Skeleton";
import type { CSSProperties } from "react";
import type { HealthDimension, HealthScore, Kpis } from "@/lib/types";

type PerformanceBand = "critical" | "watch" | "good";
type Trend = "up" | "side" | "down";

interface MetricRowData {
  icon: typeof Cloud;
  label: string;
  value: string;
  note?: string;
  band: PerformanceBand;
  detail: string;
}

interface PerformancePanel {
  title: string;
  score: number;
  target: number;
  accent: string;
  detail: string;
  rows?: MetricRowData[];
}

const BAND_STYLES: Record<PerformanceBand, { color: string }> = {
  critical: { color: "#FF1028" },
  watch: { color: "#FFB400" },
  good: { color: "#0BAE27" },
};

function clampScore(value?: number | null) {
  if (value == null || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function performanceBand(score: number): PerformanceBand {
  if (score >= 80) return "good";
  if (score >= 60) return "watch";
  return "critical";
}

function findDimension(dimensions: HealthDimension[], key: string) {
  return dimensions.find((dimension) => dimension.key === key);
}

function scoreFrom(dimension: HealthDimension | undefined, fallback = 0) {
  return clampScore(dimension?.score ?? fallback);
}

function trendFrom(score: number, target: number): Trend {
  if (score >= target + 1) return "up";
  if (score <= target - 1) return "down";
  return "side";
}

function TrendIcon({ score, target }: { score: number; target: number }) {
  const trend = trendFrom(score, target);
  const Icon = trend === "up" ? ArrowUp : trend === "side" ? ArrowRight : ArrowDown;
  const band = performanceBand(score);
  const color = trend === "side" ? "#64748B" : BAND_STYLES[band].color;
  return (
    <Icon
      size={25}
      strokeWidth={2.2}
      style={{ color }}
      aria-hidden="true"
    />
  );
}

function BandMark({ band }: { band: PerformanceBand }) {
  const color = BAND_STYLES[band].color;

  if (band === "critical") {
    return <span className="h-4 w-4 rotate-45 rounded-[2px]" style={{ backgroundColor: color }} />;
  }

  if (band === "good") {
    return <span className="h-4 w-4 rounded-full" style={{ backgroundColor: color }} />;
  }

  return <span className="h-4 w-4 rounded-[2px]" style={{ backgroundColor: color }} />;
}

function rowIconTint(band: PerformanceBand) {
  if (band === "good") return "bg-green-100 text-[#04783F]";
  if (band === "watch") return "bg-amber-50 text-[#C87500]";
  return "bg-red-50 text-[#E11D48]";
}

function rowLabelTint(band: PerformanceBand) {
  if (band === "good") return "text-[#166534]";
  if (band === "watch") return "text-[#92400E]";
  return "text-[#BE123C]";
}

function ScoreGauge({ score, target }: { score: number; target: number }) {
  const band = performanceBand(score);
  const color = BAND_STYLES[band].color;

  return (
    <div className="relative mx-auto h-[132px] w-[218px] max-w-full">
      <svg viewBox="0 0 188 112" className="h-full w-full" role="img" aria-label={`Score ${score} of 100`}>
        <path
          d="M 32 88 A 62 62 0 0 1 156 88"
          fill="none"
          stroke="#D8DEE6"
          strokeWidth="12"
          strokeLinecap="butt"
          pathLength={100}
        />
        <path
          d="M 32 88 A 62 62 0 0 1 156 88"
          fill="none"
          stroke={color}
          strokeWidth="12"
          strokeLinecap="butt"
          pathLength={100}
          strokeDasharray="100"
          strokeDashoffset={100 - score}
          className="gf-bpi-gauge-arc"
          style={{
            "--gf-bpi-offset": 100 - score,
            transition: "stroke-dashoffset 0.8s ease, stroke 0.3s ease",
          } as CSSProperties}
        />
      </svg>
      <div className="absolute inset-x-0 top-[50px] flex items-center justify-center gap-1">
        <span className="gf-bpi-score text-[36px] font-bold leading-none tabular-nums" style={{ color }}>
          {score}
        </span>
        <TrendIcon score={score} target={target} />
      </div>
      <div className="absolute inset-x-0 top-[94px] text-center text-[12px] font-medium text-slate-500">
        Goal: {target}+
      </div>
    </div>
  );
}

function extractNumber(detail: string | undefined, pattern: RegExp) {
  const match = detail?.match(pattern);
  if (!match) return 0;
  return Number(match[1] ?? 0);
}

function formatKw(value?: number | null) {
  if (value == null || Number.isNaN(value)) return "-";
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function MetricRow({ row, index }: { row: MetricRowData; index: number }) {
  const Icon = row.icon;
  return (
    <div
      className="gf-bpi-metric group/metric relative grid min-h-[74px] grid-cols-[1fr_auto] items-center gap-3 border-t border-slate-200 px-4 transition hover:bg-slate-50"
      style={{ "--gf-bpi-row-delay": `${260 + index * 70}ms` } as CSSProperties}
      tabIndex={0}
      aria-label={`${row.label}: ${row.detail}`}
      title={row.detail}
    >
      <div className="flex min-w-0 items-center gap-3">
        <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${rowIconTint(row.band)}`}>
          <Icon size={22} strokeWidth={2.2} aria-hidden="true" />
        </span>
        <span className="min-w-0">
          <span className={`block truncate text-[13px] font-semibold ${rowLabelTint(row.band)}`}>
            {row.label}
          </span>
          {row.note && <span className="block truncate text-[10px] font-medium text-slate-500">{row.note}</span>}
        </span>
      </div>
      <div className="text-right text-[13px] font-bold leading-tight text-slate-900 tabular-nums">
        {row.value}
      </div>
    </div>
  );
}

function ScorePanel({ panel, index }: { panel: PerformancePanel; index: number }) {
  const band = performanceBand(panel.score);
  return (
    <article
      className="gf-bpi-card group/card relative overflow-visible rounded-[6px] bg-white shadow-[0_2px_9px_rgba(15,23,42,0.16)] ring-1 ring-slate-200 transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_18px_38px_rgba(15,23,42,0.18)]"
      style={{ "--gf-bpi-card-delay": `${index * 85}ms` } as CSSProperties}
    >
      <div className="h-[7px] rounded-t-[6px]" style={{ backgroundColor: panel.accent }} />
      <header className="flex items-center justify-between border-b border-slate-200 bg-gradient-to-b from-slate-50 to-slate-100 px-4 py-3">
        <h3 className="text-[16px] font-bold leading-tight text-[#0F172A]">{panel.title}</h3>
        <span className="group/help relative text-slate-400 transition hover:text-teal focus-visible:text-teal" tabIndex={0}>
          <CircleHelp size={16} aria-hidden="true" />
          <span className="pointer-events-none invisible absolute right-0 top-6 z-50 w-64 rounded-xl border border-slate-200 bg-slate-950 px-3 py-2 text-[11px] font-medium leading-relaxed text-white opacity-0 shadow-xl transition group-hover/help:visible group-hover/help:opacity-100 group-focus/help:visible group-focus/help:opacity-100">
            {panel.detail}
          </span>
        </span>
      </header>
      <div className="px-3 pb-4 pt-5">
        <ScoreGauge score={panel.score} target={panel.target} />
      </div>
      {panel.rows ? (
        <div className="pb-5">
          {panel.rows.map((row, rowIndex) => (
            <MetricRow key={row.label} row={row} index={rowIndex} />
          ))}
        </div>
      ) : (
        <div className="border-t border-slate-200 px-9 pb-8 pt-6">
          <div className="mb-5 text-center text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">
            SCORING KEY
          </div>
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <BandMark band="critical" />
              <span className="text-[13px] font-medium text-slate-700">Critical 0-59</span>
            </div>
            <div className="flex items-center gap-4">
              <BandMark band="watch" />
              <span className="text-[13px] font-medium text-slate-700">Watch 60-79</span>
            </div>
            <div className="flex items-center gap-4">
              <BandMark band="good" />
              <span className="text-[13px] font-medium text-slate-700">Good 80+</span>
            </div>
          </div>
          <span className="sr-only">Current band: {band}</span>
        </div>
      )}
    </article>
  );
}

function LoadingPerformanceIndex() {
  return (
    <section className="space-y-5" aria-label="Building Performance Index loading">
      <Skeleton className="h-11 w-[480px] max-w-full rounded-[4px]" />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <Skeleton key={index} className="h-[430px] rounded-[6px]" />
        ))}
      </div>
    </section>
  );
}

function buildPanels(health: HealthScore, kpis: Kpis | null, totalKw?: number): PerformancePanel[] {
  const dimensions = health.dimensions ?? [];
  const comfort = findDimension(dimensions, "comfort");
  const air = findDimension(dimensions, "air");
  const energy = findDimension(dimensions, "energy");
  const reliability = findDimension(dimensions, "reliability");

  const overall = clampScore(health.score);
  const comfortScore = scoreFrom(comfort, overall);
  const airScore = scoreFrom(air, overall);
  const energyScore = scoreFrom(energy, overall);
  const reliabilityScore = scoreFrom(reliability, overall);
  const co2RiskZones = extractNumber(air?.detail, /(\d+)\s*>1000ppm/i);
  const co2WatchZones = extractNumber(air?.detail, /.\s*(\d+)\s+elevated/i);
  const peakRiskZones = kpis?.peak_high ?? extractNumber(energy?.detail, /(\d+)\/\d+\s+zones/i);
  const comfortHighZones = kpis?.comfort_high ?? extractNumber(comfort?.detail, /(\d+)\s+high/i);
  const comfortWatchZones = kpis?.comfort_watch ?? extractNumber(comfort?.detail, /.\s*(\d+)\s+watch/i);
  const deviceFaults = extractNumber(reliability?.detail, /(\d+)\s+device/i);
  const sensorFaults = extractNumber(reliability?.detail, /.\s*(\d+)\s+sensor/i);
  const updatedAt = health.timestamp ?? "latest replay anchor";
  const zoneCount = health.zones || 0;

  return [
    {
      title: "Overall Score",
      score: overall,
      target: 80,
      accent: "#087A3E",
      detail: `Overall live building score from /api/kpi/health-score. Higher is better. Weighted blend: Thermal Comfort 30%, Air Quality 20%, Energy Health 25%, Equipment Health 25%. Updated at ${updatedAt}.`,
    },
    {
      title: "Air Quality",
      score: airScore,
      target: 80,
      accent: "#0D63D8",
      detail: `Indoor air-quality score from /api/kpi/health-score. It penalizes the share of zones with CO2 above 1000 ppm and half-penalizes zones in the 800-1000 ppm watch band. Backend detail: ${air?.detail ?? "unavailable"}.`,
      rows: [
        {
          icon: Cloud,
          label: "CO2 Risk",
          value: `${co2RiskZones} zones`,
          note: ">1000 ppm",
          band: co2RiskZones > 0 ? "critical" : "good",
          detail: `CO2 Risk counts zones currently above 1000 ppm. These zones need ventilation or occupancy reduction first because they apply the full air-quality penalty. Source: /api/kpi/health-score. Backend detail: ${air?.detail ?? "unavailable"}.`,
        },
        {
          icon: Waves,
          label: "Elevated CO2",
          value: `${co2WatchZones} zones`,
          note: "800-1000 ppm",
          band: "watch",
          detail: `Elevated CO2 counts zones between 800 and 1000 ppm. They are not critical yet, but each zone contributes half penalty to the air-quality score and should be monitored before crossing 1000 ppm. Source: /api/kpi/health-score.`,
        },
      ],
    },
    {
      title: "Demand Health",
      score: energyScore,
      target: 85,
      accent: "#12A985",
      detail: `Demand Health is a 0-100 current peak-risk score where higher is better. It penalizes zones currently above their demand threshold, so a low score means the building needs load shifting, pre-cooling, or other demand-control actions. Backend detail: ${energy?.detail ?? "unavailable"}.`,
      rows: [
        {
          icon: Zap,
          label: "Current Demand",
          value: `${formatKw(totalKw ?? kpis?.total_kw)} kW`,
          band: energyScore >= 80 ? "good" : energyScore >= 60 ? "watch" : "critical",
          detail: `Current Demand is the whole-building electrical load at the replay/live timestamp. It uses websocket replay data when available, otherwise /api/kpi/current. Current load: ${formatKw(totalKw ?? kpis?.total_kw)} kW. Use this with Peak Risk to decide load-shed or pre-cooling actions.`,
        },
        {
          icon: AlertTriangle,
          label: "Zones at Peak Risk",
          value: zoneCount ? `${peakRiskZones}/${zoneCount}` : `${peakRiskZones}`,
          note: "above threshold",
          band: peakRiskZones > 25 ? "critical" : peakRiskZones > 0 ? "watch" : "good",
          detail: `Zones at Peak Risk counts zones marked as peak-demand risk by backend telemetry. A high share means demand is broad across the building, not isolated to one space. Source: /api/kpi/current and /api/kpi/health-score. Backend detail: ${energy?.detail ?? "unavailable"}.`,
        },
      ],
    },
    {
      title: "Thermal Comfort",
      score: comfortScore,
      target: 82,
      accent: "#0D63D8",
      detail: `Thermal-comfort score from /api/kpi/health-score. High-risk zones apply full penalty; watch zones apply half penalty. This is weighted by current occupied-zone conditions, not just average temperature. Backend detail: ${comfort?.detail ?? "unavailable"}.`,
      rows: [
        {
          icon: Thermometer,
          label: "Temp Deviation",
          value: `${comfortHighZones} zones`,
          band: comfortHighZones > 0 ? "critical" : "good",
          detail: `Temp Deviation counts zones in high thermal-comfort risk. These are the first candidates for HVAC setpoint/airflow investigation because they apply full comfort penalty. Source: /api/kpi/current. Backend detail: ${comfort?.detail ?? "unavailable"}.`,
        },
        {
          icon: Clock,
          label: "Comfort Watch",
          value: `${comfortWatchZones} zones`,
          note: "watch band",
          band: "watch",
          detail: `Comfort Watch counts zones close to the comfort limit. They apply half penalty and are useful for early intervention before occupants feel discomfort. Source: /api/kpi/current. Backend detail: ${comfort?.detail ?? "unavailable"}.`,
        },
      ],
    },
    {
      title: "Equipment Health",
      score: reliabilityScore,
      target: 85,
      accent: "#0BAE27",
      detail: `Equipment Health combines hard device faults and sensor-watch alerts from open backend alerts. Device faults are treated as hard failures; sensor_stuck is treated as a data-quality warning by affected-zone share so flat simulated temperatures do not imply every device is broken. Backend detail: ${reliability?.detail ?? "unavailable"}.`,
      rows: [
        {
          icon: Wrench,
          label: "Active Faults",
          value: `${deviceFaults} assets`,
          band: deviceFaults > 0 ? "watch" : "good",
          detail: `Active Faults counts open device_fault alerts. These are physical or operational equipment faults and carry stronger penalty than sensor-watch alerts. Source: alerts table via /api/kpi/health-score. Backend detail: ${reliability?.detail ?? "unavailable"}.`,
        },
        {
          icon: Bell,
          label: "Sensor Watch",
          value: `${sensorFaults} alerts`,
          band: "watch",
          detail: `Sensor Watch counts open sensor_stuck alerts. The rule detects zone temperature values unchanged for 120+ minutes. In simulated/replay data this is a data-quality watch signal, not proof that ${sensorFaults} physical sensors are broken. Source: anomaly engine alerts via /api/kpi/health-score.`,
        },
      ],
    },
  ];
}

export default function BuildingHealthCard({
  health,
  kpis,
  totalKw,
}: {
  health: HealthScore | null;
  kpis?: Kpis | null;
  totalKw?: number;
}) {
  if (!health) return <LoadingPerformanceIndex />;

  const panels = buildPanels(health, kpis ?? null, totalKw);

  return (
    <section className="space-y-6" aria-label="GreenFlow Building Performance Index">
      <div className="gf-bpi-heading flex flex-wrap items-center gap-4">
        <Leaf size={28} fill="#0BAE27" strokeWidth={1.8} className="gf-bpi-leaf text-[#087A3E]" aria-hidden="true" />
        <h2 className="text-[23px] font-bold tracking-[-0.03em] text-[#0F172A] md:text-[26px]">
          <span className="mr-3 text-[#087A3E]">GreenFlow</span>
          Building Performance Index
        </h2>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {panels.map((panel, index) => (
          <ScorePanel key={panel.title} panel={panel} index={index} />
        ))}
      </div>
    </section>
  );
}
