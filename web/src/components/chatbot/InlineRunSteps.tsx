"use client";

import { useEffect, useRef, useState } from "react";
import { Check, CircleAlert, Loader2, X } from "lucide-react";
import { api } from "@/lib/api";
import { titleCase } from "@/lib/format";
import type { AgentLog, AgentRun } from "@/lib/types";

/**
 * Self-contained polling widget embedded in a chat bubble. Several of these
 * can be mounted at once (one per triggered action across the conversation)
 * since each owns its own interval keyed by runId — unlike useAgentRun,
 * which tracks a single page-level run.
 */
export default function InlineRunSteps({ runId, action }: { runId: string; action?: string }) {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [running, setRunning] = useState(true);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let stopped = false;
    const poll = async () => {
      try {
        const [r, l] = await Promise.all([api.agentRun(runId), api.agentRunLogs(runId)]);
        if (stopped) return;
        setRun(r);
        setLogs(l);
        if (r.status !== "running") {
          setRunning(false);
          if (timerRef.current) clearInterval(timerRef.current);
        }
      } catch {
        /* run row may not be committed yet on the very first poll; keep trying */
      }
    };
    poll();
    timerRef.current = setInterval(poll, 1200);
    return () => {
      stopped = true;
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [runId]);

  const statusColor = running ? "text-warning"
    : run?.status === "failed" ? "text-danger" : "text-teal";

  return (
    <div className="mt-2 rounded-xl border border-border/70 bg-white px-3 py-2.5">
      <div className="mb-1.5 flex items-center justify-between">
        <p className="text-[11px] font-semibold text-text-secondary">
          {action ? titleCase(action) : "Agent run"}
        </p>
        <span className={`text-[10px] font-medium ${statusColor}`}>
          {running ? "running…" : run?.status}
        </span>
      </div>
      <ol className="space-y-1.5">
        {logs.map((log, i) => (
          <li key={`${log.step}-${i}`} className="flex items-start gap-2">
            <span className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full
              ${log.status === "completed" ? "bg-teal-light text-teal"
                : log.status === "failed" ? "bg-red-100 text-danger"
                : "bg-amber-100 text-warning"}`}>
              {log.status === "completed" ? <Check size={9} strokeWidth={3} />
                : log.status === "failed" ? <X size={9} strokeWidth={3} />
                : <CircleAlert size={9} />}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[12px] font-medium leading-tight">{log.node}</p>
              <p className="text-[11px] leading-snug text-text-muted">{log.message}</p>
            </div>
          </li>
        ))}
        {running && (
          <li className="flex items-center gap-2 pl-6 text-[11px] text-text-muted">
            <Loader2 className="h-3 w-3 animate-spin text-teal" /> working…
          </li>
        )}
      </ol>
      {run?.final_answer && !running && (
        <p className="mt-2 rounded-lg bg-teal-soft px-2.5 py-2 text-[12px] leading-relaxed text-text-primary">
          {run.final_answer}
        </p>
      )}
    </div>
  );
}
