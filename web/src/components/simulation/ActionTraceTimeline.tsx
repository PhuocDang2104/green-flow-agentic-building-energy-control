"use client";

import { Zap } from "lucide-react";
import { titleCase } from "@/lib/format";
import EmptyState from "@/components/shared/EmptyState";
import StatusPill from "@/components/shared/StatusPill";

export default function ActionTraceTimeline({ actions }: { actions: any[] }) {
  return (
    <div className="card px-5 py-4">
      <h3 className="text-sm font-semibold">Action trace (optimized run)</h3>
      {actions.length === 0 ? (
        <EmptyState title="No actions in the latest optimized run" />
      ) : (
        <ol className="mt-3 space-y-3">
          {actions.map((a, i) => (
            <li key={i} className="flex items-start gap-3">
              <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-teal-light text-teal">
                <Zap size={12} />
              </span>
              <div>
                <p className="text-[13px]">
                  <b>{String(a.start_hour ?? 0).padStart(2, "0")}:00–
                     {String(a.end_hour ?? 24).padStart(2, "0")}:00</b>{" "}
                  · {titleCase(a.action_type)}
                  <span className="ml-2">
                    <StatusPill status={a.risk || "normal"} label={`risk ${a.risk || "low"}`} />
                  </span>
                </p>
                <p className="text-xs text-text-secondary">
                  {a.reason || (a.target_zone_keys?.length
                    ? `Targets: ${a.target_zone_keys.join(", ")}`
                    : "Whole building")}
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
