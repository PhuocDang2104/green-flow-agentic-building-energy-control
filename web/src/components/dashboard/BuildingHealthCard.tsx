import { Activity } from "lucide-react";
import Skeleton from "@/components/shared/Skeleton";
import { healthBand } from "@/lib/healthBands";
import type { HealthScore } from "@/lib/types";

// theme color hexes (mirror tailwind.config) for SVG/inline styling
const STROKE: Record<string, string> = {
  success: "#16A34A", teal: "#0F766E", warning: "#F59E0B", danger: "#DC2626",
};

/**
 * Building Health Score — an OpenBlue-style composite (0-100) gauge that also
 * pinpoints which dimension is dragging the building down. Self-contained
 * polling; data from GET /api/kpi/health-score.
 */
export default function BuildingHealthCard({ health: h }: { health: HealthScore | null }) {
  const R = 54;
  const C = 2 * Math.PI * R;
  const score = h?.score ?? 0;
  const color = h?.color ?? "teal";
  const offset = C * (1 - score / 100);

  return (
    <div className="card flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center">
      {/* radial gauge */}
      <div className="flex items-center gap-4 sm:w-[252px] sm:shrink-0">
        <div className={`relative h-[128px] w-[128px] shrink-0 ${!h ? "animate-pulse" : ""}`}>
          <svg viewBox="0 0 132 132" className="h-full w-full -rotate-90">
            <circle cx="66" cy="66" r={R} fill="none" stroke="#E2E8F0" strokeWidth="11" />
            <circle
              cx="66" cy="66" r={R} fill="none" stroke={STROKE[color]} strokeWidth="11"
              strokeLinecap="round" strokeDasharray={C} strokeDashoffset={h ? offset : C}
              style={{ transition: "stroke-dashoffset 0.8s ease, stroke 0.4s ease" }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-[34px] font-semibold leading-none tracking-tight">
              {h ? score : "–"}
            </span>
            <span className="text-[11px] text-text-muted">/ 100</span>
          </div>
        </div>
        <div>
          <div className="flex items-center gap-1.5 text-[13px] font-medium text-text-secondary">
            <Activity size={15} className="text-teal" /> Building Health
          </div>
          <span
            className="mt-1.5 inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold"
            style={{ background: (STROKE[color] || "#0F766E") + "1A", color: STROKE[color] }}
          >
            {h?.grade ?? "…"}
          </span>
          <p className="mt-1 text-[11px] text-text-muted">
            {h ? `${h.zones} zones · composite index` : "loading…"}
          </p>
        </div>
      </div>

      {/* per-dimension breakdown */}
      <div className="grid flex-1 grid-cols-1 gap-x-7 gap-y-2.5 sm:grid-cols-2">
        {!h && Array.from({ length: 4 }).map((_, i) => (
          <div key={i}>
            <div className="flex items-center justify-between">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-3 w-6" />
            </div>
            <Skeleton className="mt-1.5 h-1.5 w-full" />
            <Skeleton className="mt-1.5 h-2.5 w-28" />
          </div>
        ))}
        {(h?.dimensions ?? []).map((d) => {
          const band = healthBand(d.score);
          const c = band.color;
          return (
            <div key={d.key} className="animate-fade-in"
                 title={`${band.label}: ${d.detail}. Good 70-100, Average 50-69, Warning below 50.`}>
              <div className="flex items-baseline justify-between text-[13px]">
                <span className="font-medium text-text-secondary">{d.label}</span>
                <span className="flex items-center gap-1.5">
                  <span className="rounded-full px-1.5 py-0.5 text-[9px] font-semibold"
                        style={{ color: c, background: band.softColor }}>{band.label}</span>
                  <span className="font-semibold" style={{ color: c }}>{d.score}</span>
                </span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${d.score}%`, background: c, transition: "width 0.8s ease" }}
                />
              </div>
              <p className="mt-0.5 text-[11px] text-text-muted">{d.detail}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
