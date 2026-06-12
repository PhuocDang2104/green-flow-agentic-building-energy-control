"use client";

import { fmtTime, titleCase } from "@/lib/format";
import EmptyState from "@/components/shared/EmptyState";

export default function AuditTable({ rows }: { rows: any[] }) {
  return (
    <div className="card overflow-hidden">
      <div className="border-b border-border px-5 py-3">
        <h3 className="text-sm font-semibold">Audit trail</h3>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="No audit entries yet" />
      ) : (
        <div className="max-h-72 overflow-y-auto">
          <table className="w-full text-[13px]">
            <thead className="sticky top-0 bg-surface">
              <tr className="text-left text-xs text-text-muted">
                {["Time", "Actor", "Event", "Entity"].map((h) => (
                  <th key={h} className="px-5 py-2.5 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-border/60">
                  <td className="px-5 py-2 text-text-muted">{fmtTime(r.created_at)}</td>
                  <td className="px-5 py-2">{r.actor_type}/{r.actor_id}</td>
                  <td className="px-5 py-2 font-medium">{titleCase(r.action_type)}</td>
                  <td className="px-5 py-2 text-text-secondary">{r.entity_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
