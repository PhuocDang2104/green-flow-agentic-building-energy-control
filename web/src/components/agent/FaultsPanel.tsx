"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, RefreshCw, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { fmtTime } from "@/lib/format";
import EmptyState from "@/components/shared/EmptyState";
import type { Alert } from "@/lib/types";

// alert_type -> human label (domain · condition), mirrors anomaly_rules.
const CATEGORY: Record<string, string> = {
  hvac_on_empty: "HVAC · empty zone",
  lighting_after_hours: "Lighting · after hours",
  co2_high: "Air quality · high CO₂",
  comfort_violation_sustained: "Comfort · sustained",
  sensor_stuck: "Sensor · stuck/dropout",
  device_fault: "Device · fault",
};

const SEV: Record<string, string> = {
  critical: "bg-red-100 text-danger",
  warning: "bg-amber-100 text-warning",
  info: "bg-slate-100 text-text-muted",
};

/**
 * Fault Detection & Diagnostics (FDD) — surfaces alerts written by the anomaly
 * engine. Self-contained (own polling + acknowledge + rescan).
 */
export default function FaultsPanel() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [summary, setSummary] = useState({ critical: 0, warning: 0, info: 0, total: 0 });
  const [busyId, setBusyId] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);

  const load = useCallback(() => {
    api.alerts("open").then(setAlerts).catch(() => null);
    api.alertsSummary().then(setSummary).catch(() => null);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const acknowledge = async (id: string) => {
    setBusyId(id);
    try { await api.acknowledgeAlert(id); load(); } finally { setBusyId(null); }
  };

  const rescan = async () => {
    setScanning(true);
    try { await api.scanAnomalies(); load(); } finally { setScanning(false); }
  };

  return (
    <div className="card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3">
        <div className="flex items-center gap-2">
          <AlertTriangle size={16} className="text-warning" />
          <h3 className="text-sm font-semibold">Fault Detection &amp; Diagnostics</h3>
          <span className="text-xs text-text-muted">live anomaly detection</span>
        </div>
        <div className="flex items-center gap-2">
          {summary.critical > 0 && (
            <span className="rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-semibold text-danger">
              {summary.critical} critical
            </span>
          )}
          {summary.warning > 0 && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-warning">
              {summary.warning} warning
            </span>
          )}
          {summary.info > 0 && (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-text-muted">
              {summary.info} info
            </span>
          )}
          <button onClick={rescan} disabled={scanning}
                  className="btn-secondary !px-2.5 !py-1 text-xs">
            <RefreshCw size={13} className={scanning ? "animate-spin" : ""} /> Rescan
          </button>
        </div>
      </div>

      {alerts.length === 0 ? (
        <EmptyState title="No open faults" hint="Run a scan or check back as the replay advances." />
      ) : (
        <div className="max-h-[360px] overflow-y-auto">
          <table className="w-full text-[13px]">
            <thead className="sticky top-0 bg-surface">
              <tr className="text-left text-xs text-text-muted">
                {["Zone / Equipment", "Category", "Severity", "Description", "Detected", ""].map((h) => (
                  <th key={h} className="px-4 py-2.5 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {alerts.map((a) => (
                <tr key={a.id} className="border-t border-border/60 align-top">
                  <td className="px-4 py-2.5 font-medium">{a.zone_name || a.device_name || "—"}</td>
                  <td className="px-4 py-2.5 text-text-secondary whitespace-nowrap">
                    {CATEGORY[a.alert_type] || a.alert_type}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${SEV[a.severity] || SEV.info}`}>
                      {a.severity}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-text-secondary">{a.message}</td>
                  <td className="px-4 py-2.5 text-text-muted whitespace-nowrap">{fmtTime(a.created_at)}</td>
                  <td className="px-4 py-2.5">
                    <button onClick={() => acknowledge(a.id)} disabled={busyId === a.id}
                            title="Acknowledge / resolve"
                            className="inline-flex items-center gap-1 rounded-lg border border-border px-2 py-1 text-[11px] text-text-secondary transition hover:border-teal hover:text-teal">
                      <Check size={12} /> Ack
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
