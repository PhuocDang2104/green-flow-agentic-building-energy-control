"use client";

import { Check, CircleAlert, Loader2, X } from "lucide-react";
import type { AgentLog, AgentRun } from "@/lib/types";
import { fmtTime } from "@/lib/format";
import EmptyState from "@/components/shared/EmptyState";
import StatusPill from "@/components/shared/StatusPill";

export default function AgentRunTimeline({
  run, logs, running,
}: { run: AgentRun | null; logs: AgentLog[]; running: boolean }) {
  return (
    <div className="card flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div>
          <h3 className="text-sm font-semibold">Agent run timeline</h3>
          {run && !running && (
            <p className="text-[11px] text-text-muted">
              last run · {fmtTime(run.started_at)}
            </p>
          )}
        </div>
        {run && <StatusPill status={running ? "running" : run.status} />}
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {logs.length === 0 && !running && (
          <EmptyState
            title="No run yet"
            hint="Run Optimization to watch the orchestrator execute agents step by step."
          />
        )}
        {logs.length === 0 && running && (
          <div className="flex items-center gap-2 text-sm text-text-secondary">
            <Loader2 className="h-4 w-4 animate-spin text-teal" /> Starting orchestrator…
          </div>
        )}
        <ol className="space-y-3">
          {logs.map((log, i) => (
            <li key={`${log.step}-${i}`} className="flex gap-3">
              <span className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full
                ${log.status === "completed" ? "bg-teal-light text-teal"
                  : log.status === "failed" ? "bg-red-100 text-danger"
                  : "bg-amber-100 text-warning"}`}>
                {log.status === "completed" ? <Check size={12} strokeWidth={3} />
                  : log.status === "failed" ? <X size={12} strokeWidth={3} />
                  : <CircleAlert size={12} />}
              </span>
              <div className="min-w-0">
                <p className="text-[13px] leading-snug">
                  <span className="font-semibold">{log.node}</span>
                  <span className="ml-2 text-text-muted">
                    {log.duration_ms != null ? `${log.duration_ms} ms` : ""}
                  </span>
                </p>
                <p className="text-[13px] text-text-secondary">{log.message}</p>
              </div>
            </li>
          ))}
          {running && logs.length > 0 && (
            <li className="flex items-center gap-2 pl-8 text-[13px] text-text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-teal" /> working…
            </li>
          )}
        </ol>
        {run?.final_answer && !running && (
          <div className="mt-4 rounded-xl bg-teal-soft px-4 py-3 text-[13px] leading-relaxed text-text-primary">
            {run.final_answer}
          </div>
        )}
      </div>
    </div>
  );
}
