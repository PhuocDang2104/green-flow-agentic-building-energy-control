"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { api, mediaUrl } from "@/lib/api";
import { fmtKw, fmtTemp, titleCase } from "@/lib/format";
import StatusPill from "@/components/shared/StatusPill";
import EmptyState from "@/components/shared/EmptyState";
import Skeleton from "@/components/shared/Skeleton";
import { useAppStore } from "@/stores/appStore";
import type { Camera, Device } from "@/lib/types";

export default function EntityInsightPanel() {
  const selectedEntityKey = useAppStore((s) => s.selectedEntityKey);
  const selectEntity = useAppStore((s) => s.selectEntity);
  const zoneStates = useAppStore((s) => s.zoneStates);
  const [entity, setEntity] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedEntityKey) {
      setEntity(null);
      return;
    }
    setLoading(true);
    api.entity(selectedEntityKey)
      .then(setEntity)
      .catch(() => setEntity(null))
      .finally(() => setLoading(false));
  }, [selectedEntityKey]);

  if (!selectedEntityKey) {
    return (
      <div data-tour-id="zone-inspector" className="card h-full px-5 py-4">
        <h3 className="text-sm font-semibold">Inspector</h3>
        <EmptyState
          title="Select a zone in the 3D view"
          hint="Click any zone volume to inspect state, devices and graph relations."
        />
      </div>
    );
  }

  const live = zoneStates[selectedEntityKey];
  const st = live || entity?.latest_state;

  return (
    <div data-tour-id="zone-inspector" className="card flex h-full flex-col gap-3 overflow-y-auto px-5 py-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-sm font-semibold leading-snug">
            {entity?.name || selectedEntityKey}
          </h3>
          <p className="text-xs text-text-muted">
            {titleCase(entity?.room_type)} · {entity?.entity_type || "Entity"}
          </p>
        </div>
        <button
          onClick={() => selectEntity(null)}
          className="grid h-7 w-7 place-items-center rounded-full text-text-muted hover:bg-surface-muted"
        >
          <X size={14} />
        </button>
      </div>

      {loading && <Skeleton className="h-40" />}

      {!loading && entity && (
        <>
          {entity.entity_type === "ThermalZone" && (
            <div className="grid grid-cols-2 gap-2">
              <Metric label="Temperature" value={fmtTemp(st?.temperature_c)} />
              <Metric label="Setpoint" value={st?.setpoint_c && st.setpoint_c > 0 ? fmtTemp(st.setpoint_c) : "N/A"} />
              <Metric label="Occupancy" value={`${st?.occupancy_count ?? "–"} ppl`} />
              <Metric label="Total load" value={fmtKw(st?.total_power_kw)} />
              <Metric label="HVAC" value={fmtKw(st?.hvac_power_kw)} />
              <Metric label="Lighting" value={fmtKw(st?.lighting_power_kw)} />
              <Metric label="Area" value={`${entity.area_m2 ?? "–"} m²`} />
              <Metric label="Volume" value={`${entity.volume_m3 ?? "–"} m³`} />
            </div>
          )}

          <div className="flex flex-wrap gap-1.5">
            <StatusPill status={st?.comfort_risk} label={`comfort ${st?.comfort_risk || "–"}`} />
            <StatusPill status={st?.peak_risk} label={`peak ${st?.peak_risk || "–"}`} />
            {st?.anomaly_label && <StatusPill status="high" label={titleCase(st.anomaly_label)} />}
          </div>

          {entity.cameras?.some((c: Camera) => c.video_source) && (
            <div data-tour-id="cctv-occupancy-preview">
              <h4 className="mb-1.5 text-xs font-semibold text-text-secondary">
                CCTV occupancy feed
              </h4>
              <div className="space-y-2">
                {entity.cameras
                  .filter((c: Camera) => c.video_source)
                  .map((c: Camera) => (
                    <div key={c.id} className="overflow-hidden rounded-xl border border-border/70">
                      <video
                        src={mediaUrl(c.video_source)}
                        className="w-full bg-black"
                        autoPlay
                        loop
                        muted
                        playsInline
                      />
                      <div className="flex items-center justify-between bg-surface-muted/50 px-3 py-1.5">
                        <p className="text-[11px] text-text-muted">{c.name}</p>
                        <StatusPill status="normal" label={c.privacy_mode || "count_only"} />
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {entity.devices?.length > 0 && (
            <div>
              <h4 className="mb-1.5 text-xs font-semibold text-text-secondary">
                Connected devices
              </h4>
              <div className="space-y-1.5">
                {entity.devices.map((d: Device) => (
                  <div
                    key={d.entity_key}
                    className="flex items-center justify-between rounded-xl border border-border/70 bg-surface-muted/50 px-3 py-2"
                  >
                    <div>
                      <p className="text-[13px] font-medium leading-tight">{d.name}</p>
                      <p className="text-[11px] text-text-muted">
                        {titleCase(d.device_subtype)} · {d.tag}
                      </p>
                    </div>
                    {d.controllable
                      ? <StatusPill status="normal" label="controllable" />
                      : <StatusPill status="empty" label="monitor" />}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-surface-muted/60 px-3 py-2">
      <p className="text-[11px] text-text-muted">{label}</p>
      <p className="text-[15px] font-semibold">{value}</p>
    </div>
  );
}
