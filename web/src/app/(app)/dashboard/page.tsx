"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { FileDown, Loader2 } from "lucide-react";
import PageHeader from "@/components/shell/PageHeader";
import KpiCard from "@/components/dashboard/KpiCard";
import BuildingHealthCard from "@/components/dashboard/BuildingHealthCard";
import ClimateScenarioSection from "@/components/dashboard/ClimateScenarioSection";
import Skeleton from "@/components/shared/Skeleton";
import EntityInsightPanel from "@/components/dashboard/EntityInsightPanel";
import ZoneStateTable from "@/components/dashboard/ZoneStateTable";
import { api, mediaUrl } from "@/lib/api";
import { fmtKw, fmtPct, fmtTime } from "@/lib/format";
import { healthBand, occupancyConfidenceBand } from "@/lib/healthBands";
import { useAppStore } from "@/stores/appStore";
import { usePollMs } from "@/hooks/usePollMs";
import type { HealthScore, Kpis, Zone } from "@/lib/types";

const GreenFlowViewer = dynamic(
  () => import("@/components/viewer/GreenFlowViewer"),
  { ssr: false, loading: () => <Skeleton className="h-[560px] w-full rounded-card" /> },
);

export default function DashboardPage() {
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [health, setHealth] = useState<HealthScore | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  const buildingLive = useAppStore((s) => s.buildingLive);

  const load = useCallback(() => {
    api.kpis().then(setKpis).catch(() => null);
    api.healthScore().then(setHealth).catch(() => null);
    api.zones().then(setZones).catch(() => null);
  }, []);

  const pollMs = usePollMs(30000);
  useEffect(() => {
    load();
    const t = setInterval(load, pollMs);
    return () => clearInterval(t);
  }, [load, pollMs]);

  const downloadReport = async () => {
    setReportBusy(true);
    setReportUrl(null);
    try {
      const { run_id } = await api.reportBuildingSemantic();
      // poll until the run completes, then surface the PDF link
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        const run = await api.agentRun(run_id);
        if (run.status !== "running") {
          const pdf = run.state_json?.pdf_path;
          if (pdf) setReportUrl(pdf);
          break;
        }
      }
    } finally {
      setReportBusy(false);
    }
  };

  const totalKw = buildingLive.total_power_kw ?? kpis?.total_kw;
  const occupancy = buildingLive.occupancy ?? kpis?.occupancy;
  const energyHealth = health?.dimensions.find((dimension) => dimension.key === "energy");
  const comfortHealth = health?.dimensions.find((dimension) => dimension.key === "comfort");
  const energyBand = healthBand(energyHealth?.score);
  const comfortBand = healthBand(comfortHealth?.score);
  const occupancyBand = occupancyConfidenceBand(kpis?.occ_conf);
  const updatedAt = kpis?.timestamp ? fmtTime(kpis.timestamp) : undefined;
  const zoneCount = health?.zones ?? 0;

  return (
    <div className="pb-4 elevate-surface">
      <PageHeader
        title="Dashboard & 3D View"
        subtitle="Real-time digital twin overview for zone, energy, comfort and device state."
        actions={
          <div className="flex items-center gap-2">
            {reportUrl && (
              <a href={mediaUrl(reportUrl)} target="_blank" className="btn-secondary text-[13px]">
                <FileDown size={15} /> Open PDF
              </a>
            )}
            <button onClick={downloadReport} disabled={reportBusy} className="btn-primary">
              {reportBusy ? <Loader2 size={15} className="animate-spin" /> : <FileDown size={15} />}
              {reportBusy ? "Generating…" : "Building Semantic Report"}
            </button>
          </div>
        }
      />

      <div className="mb-3">
        <BuildingHealthCard health={health} />
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiCard title="Total Load" value={fmtKw(totalKw)} loading={!kpis}
                 delta={kpis?.kwh != null ? `${Number(kpis.kwh).toFixed(0)} kWh today` : undefined}
                 status={energyBand.tone} statusLabel={health ? energyBand.label : undefined}
                 help={{
                   summary: "The sum of current power across all zones. The secondary value is calendar-day energy consumed so far.",
                   statusReason: energyHealth
                     ? `${energyBand.label}: Energy / demand score ${energyHealth.score}/100. ${energyHealth.detail}. The color follows demand risk, not the absolute kW alone.`
                     : "Demand-risk status is unavailable until the health score loads.",
                   thresholds: "Good: score 70-100. Average: 50-69. Warning: below 50. Demand score = 100 × (1 - 0.6 × peak-risk zone share).",
                   timestamp: updatedAt,
                 }} />
        <KpiCard title="Peak Risk" value={kpis?.peak_high ? "High" : "Normal"} loading={!kpis}
                 delta={`${kpis?.peak_high ?? 0} of ${zoneCount || "–"} zones at high risk`}
                 status={energyBand.tone} statusLabel={health ? energyBand.label : undefined}
                 help={{
                   summary: "Shows how many zones are currently classified as high peak-demand risk.",
                   statusReason: energyHealth
                     ? `${energyBand.label}: ${energyHealth.detail}, producing the same ${energyHealth.score}/100 Energy / demand score shown above.`
                     : "Peak-risk status is unavailable until the health score loads.",
                   thresholds: "Good: score 70-100. Average: 50-69. Warning: below 50. Each high-risk zone reduces the softened demand score.",
                   timestamp: updatedAt,
                 }} />
        <KpiCard title="Comfort" value={`${kpis?.comfort_high ?? 0} high risk`}
                 loading={!kpis}
                 delta={`${kpis?.comfort_watch ?? 0} watch`}
                 status={comfortBand.tone} statusLabel={health ? comfortBand.label : undefined}
                 help={{
                   summary: "Counts zones outside the thermal-comfort target. High-risk zones carry twice the penalty of watch zones.",
                   statusReason: comfortHealth
                     ? `${comfortBand.label}: Thermal comfort score ${comfortHealth.score}/100. ${comfortHealth.detail}. This matches the score shown above.`
                     : "Comfort status is unavailable until the health score loads.",
                   thresholds: "Good: score 70-100. Average: 50-69. Warning: below 50. Score penalty = (high + 0.5 × watch) / total zones.",
                   timestamp: updatedAt,
                 }} />
        <KpiCard title="Occupancy" value={`${occupancy ?? "–"} people`} loading={!kpis}
                 delta={kpis?.occ_conf != null ? `${fmtPct(kpis.occ_conf)} confidence` : undefined}
                 status={occupancyBand.tone} statusLabel={kpis?.occ_conf != null ? occupancyBand.label : undefined}
                 help={{
                   summary: "Estimated people currently present across the building. Count quality is expressed by occupancy confidence.",
                   statusReason: kpis?.occ_conf != null
                     ? `${occupancyBand.label}: current occupancy confidence is ${fmtPct(kpis.occ_conf)}.`
                     : "Occupancy confidence is not available.",
                   thresholds: "Good: confidence 85% or higher. Average: 70-84%. Warning: below 70%.",
                   timestamp: updatedAt,
                 }} />
      </div>

      {/* fixed-height row: the inspector matches the 3D card height and scrolls inside */}
      <div className="mt-4 grid gap-4 xl:h-[560px] xl:grid-cols-[1fr_360px]">
        <GreenFlowViewer />
        <EntityInsightPanel />
      </div>

      <div id="zone-state-table" className="mt-4 scroll-mt-4">
        <ZoneStateTable zones={zones} />
      </div>

      <ClimateScenarioSection />
    </div>
  );
}
