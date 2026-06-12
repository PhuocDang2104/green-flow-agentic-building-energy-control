"use client";

import { fmtKw, fmtTemp, titleCase } from "@/lib/format";
import StatusPill from "@/components/shared/StatusPill";
import { useAppStore } from "@/stores/appStore";
import type { Zone } from "@/lib/types";

export default function ZoneStateTable({ zones }: { zones: Zone[] }) {
  const zoneStates = useAppStore((s) => s.zoneStates);
  const selectedEntityKey = useAppStore((s) => s.selectedEntityKey);
  const selectEntity = useAppStore((s) => s.selectEntity);

  return (
    <div className="card overflow-hidden">
      <div className="border-b border-border px-5 py-3">
        <h3 className="text-sm font-semibold">Zone state</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left text-xs text-text-muted">
              {["Zone", "Type", "Occupancy", "Temp", "Load", "Comfort", "Peak"].map((h) => (
                <th key={h} className="px-5 py-2.5 font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {zones.map((z) => {
              const st = zoneStates[z.entity_key] || z.latest_state;
              const active = selectedEntityKey === z.entity_key;
              return (
                <tr
                  key={z.entity_key}
                  onClick={() => selectEntity(z.entity_key)}
                  className={`cursor-pointer border-t border-border/60 transition
                    ${active ? "bg-teal-soft" : "hover:bg-surface-muted/60"}`}
                >
                  <td className="px-5 py-2.5 font-medium">{z.name}</td>
                  <td className="px-5 py-2.5 text-text-secondary">{titleCase(z.room_type)}</td>
                  <td className="px-5 py-2.5">{st?.occupancy_count ?? "–"} ppl</td>
                  <td className="px-5 py-2.5">{fmtTemp(st?.temperature_c)}</td>
                  <td className="px-5 py-2.5">{fmtKw(st?.total_power_kw)}</td>
                  <td className="px-5 py-2.5"><StatusPill status={st?.comfort_risk} /></td>
                  <td className="px-5 py-2.5"><StatusPill status={st?.peak_risk} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
