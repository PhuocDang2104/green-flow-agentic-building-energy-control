"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ChevronRight, Loader2, ShieldAlert, X } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { api } from "@/lib/api";
import { titleCase } from "@/lib/format";
import type { AgentLog, AgentRun, Approval } from "@/lib/types";

/** Stored node label -> kind, so we can attach a rich block under that step. */
const KIND: Record<string, string> = {
  "Prediction Agent": "prediction",
  "Control Agent": "control",
  "Execution / Approval": "execution",
};
const DOT: Record<string, string> = {
  completed: "#16A34A", warning: "#F59E0B", failed: "#DC2626",
  running: "#0F766E", degraded: "#F59E0B", skipped: "#94A3B8",
};

/** Prediction node -> compact t+1 readout from the run state. */
function PredictionBlock({ st }: { st: any }) {
  const fr = st?.forecast_result;
  if (!fr) return null;
  const zones: [string, any][] = Object.entries(fr.zone_load_forecast || {}).slice(0, 4);
  const peak = st?.peak_risk?.level;
  return (
    <div className="mt-1.5 rounded-lg border border-border/55 bg-surface px-3 py-2 text-[11px]">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span>Building <b className="tabular-nums">{fr.building_load_now_kw}</b> kW
          <ChevronRight size={10} className="mx-0.5 inline text-text-muted" />
          <b className="tabular-nums text-teal">{fr.building_load_forecast_kw}</b> kW</span>
        {peak && <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
          peak === "high" ? "bg-danger/10 text-danger" : peak === "watch" ? "bg-warning/15 text-warning" : "bg-success/10 text-success"}`}>
          peak {peak}</span>}
      </div>
      {zones.length > 0 && (
        <div className="mt-1.5 space-y-1">
          {zones.map(([z, v]: any) => {
            const now = v.now_kw || 0, next = v.forecast_kw || 0, max = Math.max(now, next, 0.1);
            return (
              <div key={z} className="flex items-center gap-2">
                <span className="w-20 truncate text-[10px] text-text-muted">{z.replace(/^zone_/, "")}</span>
                <div className="relative h-2 flex-1 rounded bg-surface-muted">
                  <div className="absolute inset-y-0 left-0 rounded bg-teal/30" style={{ width: `${(next / max) * 100}%` }} />
                  <div className="absolute inset-y-0 left-0 rounded-l bg-teal/60" style={{ width: `${(now / max) * 100}%` }} />
                </div>
                <span className="w-9 text-right text-[10px] tabular-nums text-teal">{next.toFixed(1)}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Control node -> selected actions with the policy auto-review verdict. */
function ControlBlock({ st }: { st: any }) {
  const acts: any[] = st?.selected_actions || st?.final_action_plan
    || st?.ranked_actions || st?.candidate_actions || [];
  const decByType: Record<string, any> = {};
  for (const d of st?.policy_decisions || []) decByType[d.action_type || d.target || ""] = d;
  if (!acts.length) return null;
  return (
    <div className="mt-1.5 space-y-1">
      {acts.slice(0, 6).map((a: any, i: number) => {
        const dec = a.policy_decision || decByType[a.action_type]?.decision;
        const reason = a.policy_reason || (decByType[a.action_type]?.reasons || [])[0];
        const blocked = dec === "blocked" || dec === "rejected";
        const review = dec === "approval_required";
        return (
          <div key={i} className="flex items-start gap-2 rounded-lg border border-border/55 bg-surface px-2.5 py-1.5 text-[11px]">
            <span className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full ${
              blocked ? "bg-danger/10 text-danger" : review ? "bg-warning/15 text-warning" : "bg-success/10 text-success"}`}>
              {blocked ? <X size={9} /> : review ? <ShieldAlert size={9} /> : <Check size={9} />}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-medium">{a.action_type || a.type || "action"}
                {a.expected_saving_kwh != null && <span className="text-success"> &middot; -{Number(a.expected_saving_kwh).toFixed(1)} kWh</span>}
              </p>
              {(reason || dec) && <p className="text-[10px] text-text-muted">{dec}{reason ? `: ${reason}` : ""}</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Self-contained inline run trace, embedded in a chat bubble. Polls its own run
 * + logs by runId; renders the CLI node sequence with rich blocks (t+1
 * prediction, candidate actions with policy verdicts) and inline approve/reject
 * for queued actions. Several can be mounted at once across the conversation.
 */
export default function InlineRunSteps({ runId, action }: { runId: string; action?: string }) {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [running, setRunning] = useState(true);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reduce = useReducedMotion();

  const loadApprovals = useCallback(() => {
    return api.approvals("pending", runId).then(setApprovals).catch(() => null);
  }, [runId]);

  useEffect(() => {
    let stopped = false;
    setRunning(true);
    setRun(null);
    setLogs([]);
    setApprovals([]);
    setDecisionError(null);
    const poll = async () => {
      try {
        const [r, l] = await Promise.all([api.agentRun(runId), api.agentRunLogs(runId)]);
        if (stopped) return;
        setRun(r); setLogs(l);
        if (r.status !== "running") {
          setRunning(false);
          loadApprovals();
          if (timerRef.current) clearInterval(timerRef.current);
        }
      } catch { /* run row may not be committed on the first poll; keep trying */ }
    };
    poll();
    timerRef.current = setInterval(poll, 1200);
    return () => { stopped = true; if (timerRef.current) clearInterval(timerRef.current); };
  }, [runId, loadApprovals]);

  const decide = async (id: string, approve: boolean) => {
    setBusyId(id);
    setDecisionError(null);
    try {
      if (approve) await api.approve(id);
      else await api.rejectApproval(id, "rejected from chat");
      await loadApprovals();
    } catch {
      setDecisionError("Could not update this approval. Please retry.");
    } finally { setBusyId(null); }
  };

  const st = run?.state_json || {};
  const ordered = [...logs].sort((a, b) => a.step - b.step);
  const statusColor = running || run?.status === "awaiting_approval" ? "text-warning"
    : run?.status === "failed" ? "text-danger" : "text-teal";

  return (
    <div className="mt-2 rounded-xl border border-border/70 bg-surface px-3 py-2.5">
      <div className="mb-1.5 flex items-center justify-between">
        <p className="text-[11px] font-semibold text-text-secondary">
          {action ? titleCase(action) : "Agent run"}
        </p>
        <span className={`text-[10px] font-medium ${statusColor}`}>
          {running ? "running…" : run?.status}
        </span>
      </div>
      <div>
        {ordered.map((l) => {
          const kind = KIND[l.node];
          return (
            <motion.div key={`${l.step}-${l.node}`}
              initial={reduce ? false : { opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22 }} className="mb-2">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: DOT[l.status] || "#94A3B8" }} />
                <span className="text-[12px] font-medium leading-tight">{l.node}</span>
                {l.duration_ms != null && (
                  <span className="rounded bg-surface-muted px-1 py-0.5 text-[9px] tabular-nums text-text-muted">{l.duration_ms} ms</span>
                )}
              </div>
              <p className="ml-4 text-[11px] leading-snug text-text-muted">{l.message}</p>
              <div className="ml-4">
                {kind === "prediction" && <PredictionBlock st={st} />}
                {kind === "control" && <ControlBlock st={st} />}
                {kind === "execution" && approvals.length > 0 && (
                  <div className="mt-1.5 space-y-1.5">
                    {approvals.map((ap) => (
                      <div key={ap.approval_id} className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/[0.06] px-2.5 py-1.5 text-[11px]">
                        <ShieldAlert size={12} className="shrink-0 text-warning" />
                        <span className="min-w-0 flex-1 truncate">{ap.action_type || ap.reason || "Awaiting approval"}</span>
                        <button onClick={() => decide(ap.approval_id, true)} disabled={busyId === ap.approval_id}
                                className="flex items-center gap-1 rounded-md bg-success px-2 py-0.5 text-[10px] font-medium text-white transition hover:bg-success/90 disabled:opacity-50">
                          {busyId === ap.approval_id ? <Loader2 size={10} className="animate-spin" /> : <Check size={10} />} Approve
                        </button>
                        <button onClick={() => decide(ap.approval_id, false)} disabled={busyId === ap.approval_id}
                                className="flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-[10px] font-medium text-text-secondary transition hover:bg-surface-muted disabled:opacity-50">
                          <X size={10} /> Reject
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                {kind === "execution" && decisionError && (
                  <p className="mt-1.5 text-[10px] text-danger" role="alert">{decisionError}</p>
                )}
              </div>
            </motion.div>
          );
        })}
        {running && (
          <div className="flex items-center gap-2 pl-0.5 text-[11px] text-text-muted">
            <Loader2 className="h-3 w-3 animate-spin text-teal" /> working…
          </div>
        )}
      </div>
      {run?.final_answer && !running && (
        <p className="mt-2 rounded-lg bg-teal-soft px-2.5 py-2 text-[12px] leading-relaxed text-text-primary">
          {run.final_answer}
        </p>
      )}
    </div>
  );
}
