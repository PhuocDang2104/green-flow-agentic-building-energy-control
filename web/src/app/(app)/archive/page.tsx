"use client";

import { useEffect, useState } from "react";
import { Bot, FileText, FlaskConical } from "lucide-react";
import PageHeader from "@/components/shell/PageHeader";
import StatusPill from "@/components/shared/StatusPill";
import EmptyState from "@/components/shared/EmptyState";
import { api, mediaUrl } from "@/lib/api";
import { fmtTime, titleCase } from "@/lib/format";
import type { AgentRun, Report, SimulationRun } from "@/lib/types";

export default function ArchivePage() {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [sims, setSims] = useState<SimulationRun[]>([]);

  useEffect(() => {
    api.agentRuns().then(setRuns).catch(() => null);
    api.reports().then(setReports).catch(() => null);
    api.simulations().then(setSims).catch(() => null);
  }, []);

  return (
    <div className="pb-4">
      <PageHeader
        title="Archive"
        subtitle="History of agent runs, generated reports and simulation runs."
      />

      <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        <section className="card overflow-hidden">
          <Header icon={<Bot size={15} className="text-teal" />} title="Agent runs"
                  count={runs.length} />
          {runs.length === 0 ? <EmptyState title="No agent runs yet" /> : (
            <div className="max-h-[360px] overflow-y-auto">
              <table className="w-full text-[13px]">
                <thead className="sticky top-0 bg-surface">
                  <tr className="text-left text-xs text-text-muted">
                    {["Type", "Intent", "Status", "Started"].map((h) =>
                      <th key={h} className="px-5 py-2.5 font-medium">{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.id} className="border-t border-border/60">
                      <td className="px-5 py-2.5 font-medium">
                        {titleCase(r.button_action || r.entrypoint)}</td>
                      <td className="px-5 py-2.5 text-text-secondary">{titleCase(r.intent || "—")}</td>
                      <td className="px-5 py-2.5"><StatusPill status={r.status} /></td>
                      <td className="px-5 py-2.5 text-text-muted">{fmtTime(r.started_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="card overflow-hidden">
          <Header icon={<FileText size={15} className="text-teal" />} title="Reports"
                  count={reports.length} />
          {reports.length === 0 ? <EmptyState title="No reports yet" /> : (
            <div className="max-h-[360px] divide-y divide-border/60 overflow-y-auto">
              {reports.map((r) => (
                <div key={r.id} className="flex items-center justify-between gap-3 px-5 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-medium">{r.title}</p>
                    <p className="text-[11px] text-text-muted">{fmtTime(r.created_at)}</p>
                  </div>
                  {r.pdf_url && (
                    <a href={mediaUrl(r.pdf_url)} target="_blank"
                       className="btn-secondary shrink-0 !px-3 !py-1.5 text-xs">Open PDF</a>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <section className="card mt-4 overflow-hidden">
        <Header icon={<FlaskConical size={15} className="text-teal" />} title="Simulation runs"
                count={sims.length} />
        {sims.length === 0 ? <EmptyState title="No simulation runs yet" /> : (
          <div className="max-h-[320px] overflow-y-auto">
            <table className="w-full text-[13px]">
              <thead className="sticky top-0 bg-surface">
                <tr className="text-left text-xs text-text-muted">
                  {["Run", "Kind", "Engine", "Energy", "Started"].map((h) =>
                    <th key={h} className="px-5 py-2.5 font-medium">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {sims.map((s) => (
                  <tr key={s.id} className="border-t border-border/60">
                    <td className="px-5 py-2.5 font-medium">{titleCase(s.baseline_label || s.run_kind)}</td>
                    <td className="px-5 py-2.5"><StatusPill status={s.run_kind === "baseline" ? "empty" : "normal"} label={s.run_kind} /></td>
                    <td className="px-5 py-2.5 text-text-secondary">{s.engine}</td>
                    <td className="px-5 py-2.5">{s.totals ? `${s.totals.energy_kwh} kWh` : "—"}</td>
                    <td className="px-5 py-2.5 text-text-muted">{fmtTime(s.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Header({ icon, title, count }: { icon: React.ReactNode; title: string; count: number }) {
  return (
    <div className="flex items-center justify-between border-b border-border px-5 py-3">
      <h3 className="flex items-center gap-1.5 text-sm font-semibold">{icon}{title}</h3>
      <span className="pill bg-surface-muted text-text-secondary">{count}</span>
    </div>
  );
}
