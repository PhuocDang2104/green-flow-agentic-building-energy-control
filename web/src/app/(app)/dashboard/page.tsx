"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import PageHeader from "@/components/shell/PageHeader";
import BuildingHealthCard from "@/components/dashboard/BuildingHealthCard";
import ClimateScenarioSection from "@/components/dashboard/ClimateScenarioSection";
import Skeleton from "@/components/shared/Skeleton";
import EntityInsightPanel from "@/components/dashboard/EntityInsightPanel";
import ZoneStateTable from "@/components/dashboard/ZoneStateTable";
import { api } from "@/lib/api";
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

  const totalKw = buildingLive.total_power_kw ?? kpis?.total_kw;

  return (
    <div className="pb-4 elevate-surface">
      <PageHeader
        title="Dashboard & 3D View"
      />

      <div className="mb-3">
        <BuildingHealthCard health={health} kpis={kpis} totalKw={totalKw} />
      </div>

      {/* fixed-height row: the inspector matches the 3D card height and scrolls inside */}
      <div className="mt-4 grid gap-4 xl:h-[560px] xl:grid-cols-[1fr_360px]">
        <GreenFlowViewer />
        <EntityInsightPanel />
      </div>

      <div className="mt-4">
        <ZoneStateTable zones={zones} />
      </div>

      <ClimateScenarioSection />
    </div>
  );
}
