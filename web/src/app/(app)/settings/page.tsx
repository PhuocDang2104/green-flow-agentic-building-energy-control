"use client";

import { useEffect, useState } from "react";
import { Building2, Cpu, Database, ShieldCheck } from "lucide-react";
import PageHeader from "@/components/shell/PageHeader";
import PolicySummaryCard from "@/components/agent/PolicySummaryCard";
import { api } from "@/lib/api";
import type { Building } from "@/lib/types";

export default function SettingsPage() {
  const [building, setBuilding] = useState<Building | null>(null);
  const [summary, setSummary] = useState<any>(null);

  useEffect(() => {
    api.buildings().then((bs) => setBuilding(bs[0] || null)).catch(() => null);
    fetch("/api/buildings/b0000000-0000-0000-0000-000000000001/summary")
      .then((r) => r.json()).then(setSummary).catch(() => null);
  }, []);

  return (
    <div className="pb-4">
      <PageHeader title="Settings"
                  subtitle="Building, policy and platform configuration (read-only demo)." />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card icon={<Building2 size={15} className="text-teal" />} title="Building">
          <Row k="Name" v={building?.name} />
          <Row k="Location" v={building?.location_name} />
          <Row k="Type" v={building?.building_type} />
          <Row k="Floors" v={summary?.floor_count} />
          <Row k="Live zones" v={summary?.zone_count} />
          <Row k="Devices" v={summary?.device_count} />
          <Row k="Total area" v={summary?.total_area_m2 ? `${Math.round(summary.total_area_m2)} m²` : undefined} />
        </Card>

        <Card icon={<Cpu size={15} className="text-teal" />} title="Platform">
          <Row k="3D source" v="Enriched IFC (ARCH / ELE / HVAC / STRUCT)" />
          <Row k="Viewer" v="xeokit + XKT" />
          <Row k="Simulation engine" v="EnergyPlus → synthetic fallback" />
          <Row k="LLM provider" v="configurable (none / openai / anthropic)" />
          <Row k="Replay" v="WebSocket 15-min tick" />
        </Card>

        <PolicySummaryCard />

        <Card icon={<Database size={15} className="text-teal" />} title="Data">
          <Row k="Database" v="PostgreSQL 16 + pgvector" />
          <Row k="Telemetry" v="15-min, 7-day mock replay" />
          <Row k="Deploy" v="Docker Compose + Caddy" />
          <Row k="Tariff" v="EVN 3-band (VND)" />
        </Card>
      </div>
    </div>
  );
}

function Card({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="card px-5 py-4">
      <h3 className="mb-3 flex items-center gap-1.5 text-sm font-semibold">{icon}{title}</h3>
      <dl className="space-y-2">{children}</dl>
    </div>
  );
}

function Row({ k, v }: { k: string; v?: string | number }) {
  return (
    <div className="flex items-center justify-between gap-3 text-[13px]">
      <dt className="text-text-muted">{k}</dt>
      <dd className="truncate text-right font-medium text-text-primary">{v ?? "—"}</dd>
    </div>
  );
}
