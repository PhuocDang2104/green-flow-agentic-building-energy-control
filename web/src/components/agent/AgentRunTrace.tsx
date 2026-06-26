"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  Check, ChevronRight, Loader2, ShieldAlert, Sparkles, X,
} from "lucide-react";
import type { AgentLog, AgentRun, Approval } from "@/lib/types";

/** Map the stored node label to a "kind" so we can attach rich blocks. */
const KIND: Record<string, string> = {
  "Prediction Agent": "prediction",
  "Control Agent": "control",
  "Policy Engine": "policy",
  "Execution / Approval": "execution",
};

const DOT: Record<string, string> = {
  completed: "#16A34A", warning: "#F59E0B", failed: "#DC2626",
  running: "#0F766E", degraded: "#F59E0B", skipped: "#94A3B8",
};

function Dur({ ms }: { ms?: number }) {
  if (ms == null) return null;
  return <span className="rounded bg-surface-muted px-1.5 py-0.5 text-[10px] tabular-nums text-text-muted">{ms} ms</span>;
}

/** Prediction node -> compact t+1 readout from the run state. */
function PredictionBlock({ st }: { st: any }) {
  const fr = st?.forecast_result;
  if (!fr) return null;
  const zones: [string, any][] = Object.entries(fr.zone_load_forecast || {}).slice(0, 4);
  const peak = st?.peak_risk?.level;
  return (
    <div className="mt-1.5 rounded-lg border border-border/55 bg-surface px-3 py-2 text-[11.5px]">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span>Building <b className="tabular-nums">{fr.building_load_now_kw}</b> kW
          <ChevronRight size={11} className="mx-0.5 inline text-text-muted" />
          <b className="tabular-nums text-teal">{fr.building_load_forecast_kw}</b> kW</span>
        {peak && <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
          peak === "high" ? "bg-danger/10 text-danger" : peak === "watch" ? "bg-warning/15 text-warning" : "bg-success/10 text-success"}`}>
          peak risk {peak}</span>}
        {st?.forecast_confidence != null && <span className="text-text-muted">conf {Math.round(st.forecast_confidence * 100)}%</span>}
      </div>
      {zones.length > 0 && (
        <div className="mt-1.5 space-y-1">
          {zones.map(([z, v]: any) => {
            const now = v.now_kw || 0, next = v.forecast_kw || 0;
            const max = Math.max(now, next, 0.1);
            return (
              <div key={z} className="flex items-center gap-2">
                <span className="w-24 truncate text-[10.5px] text-text-muted">{z.replace(/^zone_/, "")}</span>
                <div className="relative h-2.5 flex-1 rounded bg-surface-muted">
                  <div className="absolute inset-y-0 left-0 rounded bg-teal/30" style={{ width: `${(next / max) * 100}%` }} />
                  <div className="absolute inset-y-0 left-0 rounded-l bg-teal" style={{ width: `${(now / max) * 100}%`, opacity: 0.5 }} />
                </div>
                <span className="w-10 text-right text-[10.5px] tabular-nums text-teal">{next.toFixed(1)}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Control node -> the candidate actions with the policy auto-review verdict. */
function ControlBlock({ st }: { st: any }) {
  const acts: any[] = st?.selected_actions || st?.final_action_plan
    || st?.ranked_actions || st?.candidate_actions || [];
  const decByType: Record<string, any> = {};
  for (const d of st?.policy_decisions || []) decByType[d.action_type || d.target || ""] = d;
  if (!acts.length) return null;
  return (
    <div className="mt-1.5 space-y-1">
      {acts.slice(0, 8).map((a: any, i: number) => {
        const dec = a.policy_decision || decByType[a.action_type]?.decision;
        const reason = a.policy_reason || (decByType[a.action_type]?.reasons || [])[0];
        const blocked = dec === "blocked" || dec === "rejected";
        const review = dec === "approval_required";
        return (
          <div key={i} className="flex items-start gap-2 rounded-lg border border-border/55 bg-surface px-3 py-1.5 text-[11.5px]">
            <span className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full ${
              blocked ? "bg-danger/10 text-danger" : review ? "bg-warning/15 text-warning" : "bg-success/10 text-success"}`}>
              {blocked ? <X size={10} /> : review ? <ShieldAlert size={10} /> : <Check size={10} />}
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-medium">{a.action_type || a.type || "action"}
                {a.target_name && <span className="text-text-muted"> &middot; {a.target_name}</span>}
                {a.expected_saving_kwh != null && <span className="text-success"> &middot; -{Number(a.expected_saving_kwh).toFixed(1)} kWh</span>}
              </p>
              {(reason || dec) && <p className="text-[10.5px] text-text-muted">{dec}{reason ? `: ${reason}` : ""}</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Execution node -> inline approve / reject for the queued actions. */
function ApprovalBlock({ approvals, onApprove, onReject, busyId }: {
  approvals: Approval[]; onApprove: (id: string) => void; onReject: (id: string) => void; busyId: string | null;
}) {
  if (!approvals.length) return null;
  return (
    <div className="mt-1.5 space-y-1.5">
      {approvals.map((ap) => (
        <div key={ap.approval_id} className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/[0.06] px-3 py-2 text-[11.5px]">
          <ShieldAlert size={13} className="shrink-0 text-warning" />
          <span className="min-w-0 flex-1 truncate">{ap.action_type || ap.reason || "Action awaiting approval"}</span>
          <button onClick={() => onApprove(ap.approval_id)} disabled={busyId === ap.approval_id}
                  className="flex items-center gap-1 rounded-md bg-success px-2 py-1 text-[11px] font-medium text-white transition hover:bg-success/90 disabled:opacity-50">
            {busyId === ap.approval_id ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />} Approve
          </button>
          <button onClick={() => onReject(ap.approval_id)} disabled={busyId === ap.approval_id}
                  className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] font-medium text-text-secondary transition hover:bg-surface-muted disabled:opacity-50">
            <X size={11} /> Reject
          </button>
        </div>
      ))}
    </div>
  );
}

/**
 * CLI-style agent run trace: every orchestration node streams in as a line with
 * its timing and message, and select nodes expand inline rich blocks - the t+1
 * prediction, the candidate actions with the policy auto-review, and inline
 * approve / reject for queued actions. Mirrors a coding-agent CLI.
 */
export default function AgentRunTrace({
  run, logs, running, approvals, onApprove, onReject, busyId,
}: {
  run: AgentRun | null; logs: AgentLog[]; running: boolean;
  approvals: Approval[]; onApprove: (id: string) => void; onReject: (id: string) => void; busyId: string | null;
}) {
  const reduce = useReducedMotion();
  const st = run?.state_json || {};
  const ordered = [...logs].sort((a, b) => a.step - b.step);

  if (!logs.length && !running) {
    return (
      <div className="grid flex-1 place-items-center px-6 text-center">
        <div>
          <Sparkles size={22} className="mx-auto text-teal/60" />
          <p className="mt-2 text-[13px] font-medium">No run yet</p>
          <p className="mt-1 text-[12px] text-text-muted">Run Optimization or Prediction to watch the agent reason step by step.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-3 font-mono">
      <AnimatePresence initial={false}>
        {ordered.map((l) => {
          const kind = KIND[l.node];
          return (
            <motion.div key={`${l.step}-${l.node}`}
              initial={reduce ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25 }} className="mb-2.5">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: DOT[l.status] || "#94A3B8" }} />
                <span className="text-[12.5px] font-semibold tracking-tight">{l.node}</span>
                <Dur ms={l.duration_ms} />
              </div>
              <p className="ml-4 mt-0.5 text-[12px] leading-relaxed text-text-secondary">{l.message}</p>
              <div className="ml-4">
                {kind === "prediction" && <PredictionBlock st={st} />}
                {kind === "control" && <ControlBlock st={st} />}
                {kind === "execution" && (
                  <ApprovalBlock approvals={approvals} onApprove={onApprove} onReject={onReject} busyId={busyId} />
                )}
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>

      {running && (
        <div className="ml-0.5 flex items-center gap-2 text-[12px] text-text-muted">
          <Loader2 size={13} className="animate-spin text-teal" /> running…
        </div>
      )}
      {!running && run?.final_answer && (
        <div className="mt-2 rounded-lg bg-teal-soft px-3 py-2 text-[12px] leading-relaxed text-teal">
          {run.final_answer}
        </div>
      )}
    </div>
  );
}
