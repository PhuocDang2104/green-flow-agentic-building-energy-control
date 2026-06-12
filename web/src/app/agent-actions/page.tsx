"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Play, TrendingUp } from "lucide-react";
import PageHeader from "@/components/shell/PageHeader";
import AgentRunTimeline from "@/components/agent/AgentRunTimeline";
import ActionQueue from "@/components/agent/ActionQueue";
import PredictionPanel from "@/components/agent/PredictionPanel";
import PolicySummaryCard from "@/components/agent/PolicySummaryCard";
import AuditTable from "@/components/agent/AuditTable";
import { useAgentRun } from "@/hooks/useAgentRun";
import { api } from "@/lib/api";
import type { ActionItem, Approval } from "@/lib/types";

export default function AgentActionsPage() {
  const { run, logs, running, start } = useAgentRun();
  const [actions, setActions] = useState<ActionItem[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [audit, setAudit] = useState<any[]>([]);
  const [busyApproval, setBusyApproval] = useState<string | null>(null);
  const [horizon, setHorizon] = useState(60);
  const [autoAction, setAutoAction] = useState(true);

  const refresh = useCallback(() => {
    api.actions().then(setActions).catch(() => null);
    api.approvals().then(setApprovals).catch(() => null);
    api.auditLog().then(setAudit).catch(() => null);
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 15000);
    return () => clearInterval(t);
  }, [refresh]);

  // refresh queue when a run finishes
  useEffect(() => {
    if (!running && run) refresh();
  }, [running, run, refresh]);

  const scenario = { horizon_minutes: horizon, allow_auto_action: autoAction };

  const decide = async (id: string, approve: boolean) => {
    setBusyApproval(id);
    try {
      if (approve) await api.approve(id);
      else await api.rejectApproval(id, "rejected from UI");
      refresh();
    } finally {
      setBusyApproval(null);
    }
  };

  return (
    <div className="pb-4">
      <PageHeader
        title="Agents & Actions"
        subtitle="Run the orchestrator, watch agents execute, review and approve actions."
        actions={
          <>
            <button className="btn-secondary" disabled={running}
                    onClick={() => start(() => api.runPrediction(scenario))}>
              <TrendingUp size={15} /> Run Prediction
            </button>
            <button className="btn-primary" disabled={running}
                    onClick={() => start(() => api.runOptimization(scenario))}>
              {running ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
              Run Optimization
            </button>
          </>
        }
      />

      <div className="card mb-4 flex flex-wrap items-center gap-5 px-5 py-3 text-[13px]">
        <label className="flex items-center gap-2">
          <span className="text-text-secondary">Forecast horizon</span>
          <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}
                  className="rounded-lg border border-border px-2 py-1">
            {[15, 30, 60].map((h) => <option key={h} value={h}>{h} min</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2">
          <span className="text-text-secondary">Scope</span>
          <select className="rounded-lg border border-border px-2 py-1">
            <option>Whole building</option>
            <option>Storey 0</option>
          </select>
        </label>
        <label className="flex cursor-pointer items-center gap-2">
          <input type="checkbox" checked={autoAction}
                 onChange={(e) => setAutoAction(e.target.checked)}
                 className="h-3.5 w-3.5 accent-teal" />
          <span className="text-text-secondary">Allow auto-actions</span>
        </label>
        <span className="ml-auto text-xs text-text-muted">
          Every action is simulated and policy-checked before execution.
        </span>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
        <div className="min-h-[420px]">
          <AgentRunTimeline run={run} logs={logs} running={running} />
        </div>
        <div className="min-h-[420px]">
          <ActionQueue
            actions={actions}
            approvals={approvals}
            onApprove={(id) => decide(id, true)}
            onReject={(id) => decide(id, false)}
            busyId={busyApproval}
          />
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <PredictionPanel run={run} />
        <PolicySummaryCard />
        <AuditTable rows={audit.slice(0, 30)} />
      </div>
    </div>
  );
}
