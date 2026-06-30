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
        Target: {target}
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
    >
      <div className="flex min-w-0 items-center gap-3">
        <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${rowIconTint(row.band)}`}>
          <Icon size={22} strokeWidth={2.2} aria-hidden="true" />
        </span>
        <span className="min-w-0">
          <span className="block truncate text-[13px] font-semibold text-[#166534]">{row.label}</span>
          {row.note && <span className="block truncate text-[10px] font-medium text-slate-500">{row.note}</span>}
        </span>
      </div>
      <div className="text-right text-[13px] font-bold leading-tight text-slate-900 tabular-nums">
        {row.value}
      </div>
      <div className="pointer-events-none invisible absolute left-4 right-4 top-[calc(100%-5px)] z-40 translate-y-1 rounded-xl border border-slate-200 bg-slate-950 px-3 py-2 text-[11px] leading-relaxed text-white opacity-0 shadow-xl transition group-hover/metric:visible group-hover/metric:translate-y-0 group-hover/metric:opacity-100 group-focus/metric:visible group-focus/metric:translate-y-0 group-focus/metric:opacity-100">
        {row.detail}
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
        <span className="relative text-slate-400 transition group-hover/card:text-teal">
          <CircleHelp size={16} aria-hidden="true" />
          <span className="pointer-events-none invisible absolute right-0 top-6 z-50 w-64 rounded-xl border border-slate-200 bg-slate-950 px-3 py-2 text-[11px] font-medium leading-relaxed text-white opacity-0 shadow-xl transition group-hover/card:visible group-hover/card:opacity-100">
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

  return [
    {
      title: "Overall Score",
      score: overall,
      target: 80,
      accent: "#087A3E",
      detail: `Composite score from live backend dimensions: comfort, air quality, energy demand and equipment reliability. Backend timestamp: ${health.timestamp ?? "latest replay anchor"}.`,
    },
    {
      title: "Air Quality",
      score: airScore,
      target: 80,
      accent: "#0D63D8",
      detail: air?.detail ?? "Live CO2 risk score from /api/kpi/health-score.",
      rows: [
        {
          icon: Cloud,
          label: "CO2 Risk",
          value: `${co2RiskZones} zones`,
          note: ">1000 ppm",
          band: co2RiskZones > 0 ? "critical" : "good",
          detail: air?.detail ?? "Zones above 1000 ppm from backend health-score detail.",
        },
        {
          icon: Waves,
          label: "Elevated CO2",
          value: `${co2WatchZones} zones`,
          note: "800-1000 ppm",
          band: co2WatchZones > 0 ? "watch" : "good",
          detail: air?.detail ?? "Zones in CO2 watch band from backend health-score detail.",
        },
      ],
    },
    {
      title: "Energy / Demand",
      score: energyScore,
      target: 85,
      accent: "#12A985",
      detail: energy?.detail ?? "Live demand-risk score from /api/kpi/health-score.",
      rows: [
        {
          icon: Zap,
          label: "Peak Demand",
          value: `${formatKw(totalKw ?? kpis?.total_kw)} kW`,
          band: energyScore >= 80 ? "good" : energyScore >= 60 ? "watch" : "critical",
          detail: `Current total load from /api/kpi/current or websocket replay: ${formatKw(totalKw ?? kpis?.total_kw)} kW.`,
        },
        {
          icon: AlertTriangle,
          label: "Peak Risk",
          value: `${peakRiskZones} zones`,
          note: "above threshold",
          band: peakRiskZones > 0 ? "watch" : "good",
          detail: energy?.detail ?? "Peak-risk zone count from backend health-score detail.",
        },
      ],
    },
    {
      title: "Thermal Comfort",
      score: comfortScore,
      target: 82,
      accent: "#0D63D8",
      detail: comfort?.detail ?? "Live comfort-risk score from /api/kpi/health-score.",
      rows: [
        {
          icon: Thermometer,
          label: "Temp Deviation",
          value: `${comfortHighZones} zones`,
          band: comfortHighZones > 0 ? "critical" : "good",
          detail: comfort?.detail ?? "High comfort-risk zone count from /api/kpi/current.",
        },
        {
          icon: Clock,
          label: "Comfort Watch",
          value: `${comfortWatchZones} zones`,
          note: "watch band",
          band: comfortWatchZones > 0 ? "watch" : "good",
          detail: comfort?.detail ?? "Watch comfort-risk zone count from /api/kpi/current.",
        },
      ],
    },
    {
      title: "Equipment Health",
      score: reliabilityScore,
      target: 85,
      accent: "#0BAE27",
      detail: reliability?.detail ?? "Live equipment and sensor fault score from /api/kpi/health-score.",
      rows: [
        {
          icon: Wrench,
          label: "Active Faults",
          value: `${deviceFaults} assets`,
          band: deviceFaults > 0 ? "watch" : "good",
          detail: reliability?.detail ?? "Open device faults from backend alerts.",
        },
        {
          icon: Bell,
          label: "Sensor Watch",
          value: `${sensorFaults} alerts`,
          band: sensorFaults > 0 ? "watch" : "good",
          detail: reliability?.detail ?? "Open sensor watch alerts from backend.",
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
