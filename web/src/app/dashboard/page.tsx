"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { FileDown, Loader2 } from "lucide-react";
import PageHeader from "@/components/shell/PageHeader";
import KpiCard from "@/components/dashboard/KpiCard";
import EntityInsightPanel from "@/components/dashboard/EntityInsightPanel";
import ZoneStateTable from "@/components/dashboard/ZoneStateTable";
import { api, mediaUrl } from "@/lib/api";
import { fmtKw, fmtPct } from "@/lib/format";
import { useAppStore } from "@/stores/appStore";
import type { Kpis, Zone } from "@/lib/types";

const GreenFlowViewer = dynamic(
  () => import("@/components/viewer/GreenFlowViewer"),
  { ssr: false, loading: () => <div className="card h-[560px] animate-pulse" /> },
);

export default function DashboardPage() {
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  const buildingLive = useAppStore((s) => s.buildingLive);

  const load = useCallback(() => {
    api.kpis().then(setKpis).catch(() => null);
    api.zones().then(setZones).catch(() => null);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

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

  return (
    <div className="pb-4">
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

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <KpiCard title="Total Load" value={fmtKw(totalKw)}
                 delta={kpis?.kwh != null ? `${Number(kpis.kwh).toFixed(0)} kWh today` : undefined}
                 status="normal" />
        <KpiCard title="Peak Risk" value={kpis?.peak_high ? "High" : "Normal"}
                 delta={`${kpis?.peak_high ?? 0} zones in peak watch`}
                 status={kpis?.peak_high ? "warning" : "success"} />
        <KpiCard title="Comfort" value={`${(kpis?.comfort_watch ?? 0) + (kpis?.comfort_high ?? 0)} watch`}
                 delta={`${kpis?.comfort_high ?? 0} high risk`}
                 status={kpis?.comfort_high ? "danger" : "success"} />
        <KpiCard title="Occupancy" value={`${occupancy ?? "–"} people`}
                 delta={kpis?.occ_conf != null ? `${fmtPct(kpis.occ_conf)} confidence` : undefined}
                 status="info" />
        <KpiCard title="Agent Actions" value={`${kpis?.executed ?? 0} executed`}
                 delta={`${kpis?.pending ?? 0} pending approval`}
                 status={kpis?.pending ? "warning" : "success"} />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_360px]">
        <GreenFlowViewer />
        <EntityInsightPanel />
      </div>

      <div className="mt-4">
        <ZoneStateTable zones={zones} />
      </div>
    </div>
  );
}
