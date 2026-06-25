"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, MessageSquare, Play, Plus, TrendingUp } from "lucide-react";
import PageHeader from "@/components/shell/PageHeader";
import AgentRunTimeline from "@/components/agent/AgentRunTimeline";
import ActionQueue from "@/components/agent/ActionQueue";
import PredictionPanel from "@/components/agent/PredictionPanel";
import PolicySummaryCard from "@/components/agent/PolicySummaryCard";
import AuditTable from "@/components/agent/AuditTable";
import FaultsPanel from "@/components/agent/FaultsPanel";
import BuildingHealthCard from "@/components/dashboard/BuildingHealthCard";
import EnergyAnalyticsSection from "@/components/dashboard/EnergyAnalyticsSection";
import ChatThread from "@/components/chatbot/ChatThread";
import { usePollMs } from "@/hooks/usePollMs";
import { useAgentRun } from "@/hooks/useAgentRun";
import { api } from "@/lib/api";
import type { ActionItem, Approval, ChatSessionSummary } from "@/lib/types";

export default function AgentActionsPage() {
  const { run, logs, running, start, loadLatest } = useAgentRun();
  const hydrated = useRef(false);
  const [actions, setActions] = useState<ActionItem[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [audit, setAudit] = useState<any[]>([]);
  const [busyApproval, setBusyApproval] = useState<string | null>(null);
  const [horizon] = useState(60);
  const [autoAction] = useState(true);

  // chat sessions (left rail) — IDE-style explorer
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const loadSessions = useCallback(() => {
    api.chatSessions().then(setSessions).catch(() => null);
  }, []);

  const refresh = useCallback(() => {
    api.actions().then(setActions).catch(() => null);
    api.approvals().then(setApprovals).catch(() => null);
    api.auditLog().then(setAudit).catch(() => null);
  }, []);

  const pollMs = usePollMs(15000);
  useEffect(() => {
    refresh();
    loadSessions();
    const t = setInterval(() => { refresh(); loadSessions(); }, pollMs);
    return () => clearInterval(t);
  }, [refresh, loadSessions, pollMs]);

  useEffect(() => {
    if (hydrated.current) return;
    hydrated.current = true;
    loadLatest();
  }, [loadLatest]);

  // when a run finishes it posts a report into the active session → refresh both
  useEffect(() => {
    if (!running && run) { refresh(); loadSessions(); }
  }, [running, run, refresh, loadSessions]);

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

  const onSessionId = (id: string) => {
    setSessionId(id);
    loadSessions();
  };
  const activeSession = sessions.find((s) => s.id === sessionId) || null;
  const fmtDate = (s: string) => new Date(s).toLocaleDateString("vi-VN");

  return (
    <div className="pb-4">
      <PageHeader
        title="Agents & Actions"
        subtitle="An IDE for the building agent — sessions, live building state, chat & action queue."
        actions={
          <>
            <button className="btn-secondary" disabled={running}
                    onClick={() => start(() => api.runPrediction(scenario, sessionId))}>
              <TrendingUp size={15} /> Run Prediction
            </button>
            <button className="btn-primary" disabled={running}
                    onClick={() => start(() => api.runOptimization(scenario, sessionId))}>
              {running ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
              Run Optimization
            </button>
          </>
        }
      />

      {/* IDE 3-pane: sessions · building state · copilot (chat + actions) ------- */}
      <div className="grid gap-3 lg:grid-cols-[220px_1fr_400px]">
        {/* left: session explorer */}
        <aside className="card flex h-[720px] flex-col p-0">
          <div className="flex items-center justify-between border-b border-border px-3 py-2.5">
            <span className="text-[13px] font-semibold">Sessions</span>
            <button
              onClick={() => setSessionId(null)}
              title="New session"
              className="flex items-center gap-1 rounded-lg px-2 py-1 text-[12px] font-medium text-teal hover:bg-teal-soft"
            >
              <Plus size={14} /> New
            </button>
          </div>
          <div className="flex-1 space-y-0.5 overflow-y-auto px-2 py-2">
            {sessions.length === 0 && (
              <p className="px-2 py-3 text-[12px] text-text-muted">
                No conversations yet. Ask the copilot →
              </p>
            )}
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => setSessionId(s.id)}
                className={`block w-full rounded-lg px-2.5 py-2 text-left transition hover:bg-surface-muted
                  ${s.id === sessionId ? "bg-teal-soft" : ""}`}
              >
                <p className={`truncate text-[12.5px] ${s.id === sessionId ? "font-medium text-teal" : "text-text-secondary"}`}>
                  {s.first_message || "New conversation"}
                </p>
                <p className="mt-0.5 text-[11px] text-text-muted">
                  {s.n_messages} msgs · {fmtDate(s.created_at)}
                </p>
              </button>
            ))}
          </div>
        </aside>

        {/* middle: live building state / metrics */}
        <section className="h-[720px] overflow-y-auto pr-0.5">
          <div className="space-y-3">
            <BuildingHealthCard />
            <EnergyAnalyticsSection />
            <FaultsPanel />
          </div>
        </section>

        {/* right: copilot — chat (with per-session agent reports) + action queue */}
        <aside className="flex h-[720px] flex-col gap-3">
          <section className="card flex min-h-0 flex-[3] flex-col p-0">
            <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
              <span className="grid h-7 w-7 place-items-center rounded-full bg-teal text-white">
                <MessageSquare size={13} />
              </span>
              <div className="min-w-0">
                <p className="truncate text-[13px] font-semibold">
                  {activeSession?.first_message || "Copilot"}
                </p>
                <p className="text-[11px] text-text-muted">
                  {activeSession
                    ? `${activeSession.n_messages} messages · ${fmtDate(activeSession.created_at)}`
                    : "Agent reports notable events here after each run"}
                </p>
              </div>
            </div>
            <ChatThread sessionId={sessionId} onSessionId={onSessionId} />
          </section>
          <div className="flex min-h-0 flex-[2] flex-col">
            <ActionQueue
              actions={actions}
              approvals={approvals}
              onApprove={(id) => decide(id, true)}
              onReject={(id) => decide(id, false)}
              busyId={busyApproval}
            />
          </div>
        </aside>
      </div>

      {/* bottom panel: agent run output (timeline + prediction + policy + audit) */}
      <div className="mt-3">
        <AgentRunTimeline run={run} logs={logs} running={running} />
      </div>
      <div className="mt-3 grid gap-3 lg:grid-cols-3">
        <PredictionPanel run={run} />
        <PolicySummaryCard />
        <AuditTable rows={audit.slice(0, 30)} />
      </div>
    </div>
  );
}
