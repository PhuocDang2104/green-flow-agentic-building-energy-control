import { ArrowDown, ArrowRight } from "lucide-react";
import Skeleton from "@/components/shared/Skeleton";
import type { HealthDimension, HealthScore } from "@/lib/types";

type PerformanceBand = "poor" | "average" | "good";

interface ScoreRow {
  label: string;
  score: number;
  detail?: string;
}

interface PerformancePanel {
  title: string;
  score: number;
  target: number;
  accent: string;
  rows?: ScoreRow[];
}

const BAND_STYLES: Record<PerformanceBand, { color: string }> = {
  poor: { color: "#E11D48" },
  average: { color: "#FBBF24" },
  good: { color: "#16C172" },
};

function clampScore(value?: number | null) {
  if (value == null || Number.isNaN(value)) return 0;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function performanceBand(score: number): PerformanceBand {
  if (score >= 90) return "good";
  if (score >= 75) return "average";
  return "poor";
}

function average(scores: Array<number | undefined>) {
  const available = scores.filter((score): score is number => score != null);
  if (!available.length) return 0;
  return clampScore(available.reduce((sum, score) => sum + score, 0) / available.length);
}

function findDimension(dimensions: HealthDimension[], key: string) {
  return dimensions.find((dimension) => dimension.key === key);
}

function scoreFrom(dimension: HealthDimension | undefined, fallback = 0) {
  return clampScore(dimension?.score ?? fallback);
}

function TargetIcon({ score, target }: { score: number; target: number }) {
  const isStable = score >= target;
  const Icon = isStable ? ArrowRight : ArrowDown;
  return (
    <Icon
      size={24}
      strokeWidth={2.2}
      className={isStable ? "text-slate-500" : "text-rose-500"}
      aria-hidden="true"
    />
  );
}

function BandMark({ band }: { band: PerformanceBand }) {
  const color = BAND_STYLES[band].color;

  if (band === "poor") {
    return <span className="h-4 w-4 rotate-45 rounded-[2px]" style={{ backgroundColor: color }} />;
  }

  if (band === "good") {
    return <span className="h-4 w-4 rounded-full" style={{ backgroundColor: color }} />;
  }

  return <span className="h-4 w-4 rounded-[2px]" style={{ backgroundColor: color }} />;
}

function ScoreGauge({ score, target }: { score: number; target: number }) {
  const band = performanceBand(score);
  const color = BAND_STYLES[band].color;

  return (
    <div className="relative mx-auto h-[118px] w-[188px]">
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
          style={{ transition: "stroke-dashoffset 0.8s ease, stroke 0.3s ease" }}
        />
      </svg>
      <div className="absolute inset-x-0 top-[46px] flex items-center justify-center gap-1">
        <span className="text-[38px] font-medium leading-none text-slate-700 tabular-nums">{score}</span>
        <TargetIcon score={score} target={target} />
      </div>
      <div className="absolute inset-x-0 top-[88px] text-center text-[14px] font-semibold text-slate-400">
        Target: {target}
      </div>
    </div>
  );
}

function MetricRow({ row }: { row: ScoreRow }) {
  const band = performanceBand(row.score);

  return (
    <div className="grid min-h-[50px] grid-cols-[1fr_auto] items-center border-t border-slate-200 px-4">
      <div className="flex min-w-0 items-center gap-3">
        <BandMark band={band} />
        <span className="truncate text-[15px] font-semibold text-[#355D8B]" title={row.detail}>
          {row.label}
        </span>
      </div>
      <div className="flex items-center gap-3 text-[16px] font-semibold text-slate-500 tabular-nums">
        <span>{row.score}</span>
        <TargetIcon score={row.score} target={75} />
      </div>
    </div>
  );
}

function ScorePanel({ panel }: { panel: PerformancePanel }) {
  return (
    <article className="overflow-hidden rounded-[6px] bg-white shadow-[0_2px_9px_rgba(15,23,42,0.16)] ring-1 ring-slate-200">
      <div className="h-[7px]" style={{ backgroundColor: panel.accent }} />
      <header className="border-b border-slate-200 bg-gradient-to-b from-slate-50 to-slate-100 px-4 py-3">
        <h3 className="text-[20px] font-semibold leading-tight text-slate-700">{panel.title}</h3>
      </header>
      <div className="px-3 pb-4 pt-5">
        <ScoreGauge score={panel.score} target={panel.target} />
      </div>
      {panel.rows ? (
        <div className="pb-4">
          {panel.rows.map((row) => (
            <MetricRow key={row.label} row={row} />
          ))}
        </div>
      ) : (
        <div className="px-9 pb-8 pt-1">
          <div className="mb-4 text-center text-[13px] font-semibold uppercase tracking-[0.22em] text-slate-400">
            Scoring Key
          </div>
          <div className="space-y-3">
            <div className="flex items-center gap-4">
              <BandMark band="poor" />
              <span className="text-[15px] font-semibold text-slate-500">Poor 0-74</span>
            </div>
            <div className="flex items-center gap-4">
              <BandMark band="average" />
              <span className="text-[15px] font-semibold text-slate-500">Average 75-89</span>
            </div>
            <div className="flex items-center gap-4">
              <BandMark band="good" />
              <span className="text-[15px] font-semibold text-slate-500">Good 90+</span>
            </div>
          </div>
        </div>
      )}
    </article>
  );
}

function LoadingPerformanceIndex() {
  return (
    <section className="space-y-3" aria-label="Building Performance Index loading">
      <Skeleton className="h-7 w-60 rounded-[4px]" />
      <div className="grid gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-[356px] rounded-[6px]" />
        ))}
      </div>
    </section>
  );
}

function buildPanels(health: HealthScore): PerformancePanel[] {
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
  const peopleScore = average([comfortScore, airScore]);
  const placesScore = average([reliabilityScore, energyScore]);
  const planetScore = energyScore;

  return [
    {
      title: "Overall Score",
      score: overall,
      target: 75,
      accent: "#0F2D52",
    },
    {
      title: "People",
      score: peopleScore,
      target: 75,
      accent: "#0B6FA4",
      rows: [
        { label: comfort?.label ?? "Thermal comfort", score: comfortScore, detail: comfort?.detail },
        { label: air?.label ?? "Air quality", score: airScore, detail: air?.detail },
      ],
    },
    {
      title: "Places",
      score: placesScore,
      target: 75,
      accent: "#0EA5E9",
      rows: [
        { label: reliability?.label ?? "Equipment reliability", score: reliabilityScore, detail: reliability?.detail },
        { label: energy?.label ?? "Energy / demand", score: energyScore, detail: energy?.detail },
      ],
    },
    {
      title: "Planet",
      score: planetScore,
      target: 75,
      accent: "#16A34A",
      rows: [
        { label: energy?.label ?? "Energy / demand", score: energyScore, detail: energy?.detail },
      ],
    },
  ];
}

export default function BuildingHealthCard({ health }: { health: HealthScore | null }) {
  if (!health) return <LoadingPerformanceIndex />;

  const panels = buildPanels(health);

  return (
    <section className="space-y-3" aria-label="Building Performance Index">
      <h2 className="text-[20px] font-semibold tracking-[-0.01em] text-slate-800">
        Building Performance Index
      </h2>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {panels.map((panel) => (
          <ScorePanel key={panel.title} panel={panel} />
        ))}
      </div>
    </section>
  );
}
