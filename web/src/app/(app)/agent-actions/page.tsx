"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertTriangle, Bot, ClipboardCheck, Loader2, Play, Plus, Trash2, TrendingUp,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import PageHeader from "@/components/shell/PageHeader";
import AgentRunTimeline from "@/components/agent/AgentRunTimeline";
import ActionQueue from "@/components/agent/ActionQueue";
import PredictionPanel from "@/components/agent/PredictionPanel";
import PolicySummaryCard from "@/components/agent/PolicySummaryCard";
import AuditTable from "@/components/agent/AuditTable";
import ChatThread, { type ChatRunEvent } from "@/components/chatbot/ChatThread";
import { usePollMs } from "@/hooks/usePollMs";
import { useAgentRun } from "@/hooks/useAgentRun";
import { api } from "@/lib/api";
import { displayPromptInEnglish } from "@/lib/constants";
import type { ActionItem, Approval, ChatSessionSummary } from "@/lib/types";

/** One glanceable stat for the status line (plain inline, no card). The value
 *  springs in when it changes; `live` adds a pulsing dot for real running state. */
function Stat({ icon: Icon, label, value, alert, live }: {
  icon: typeof Bot; label: string; value: string | number; alert?: boolean; live?: boolean;
}) {
  const reduce = useReducedMotion();
  return (
    <span className="flex items-center gap-1.5">
      <Icon size={14} className={alert ? "text-warning" : "text-text-muted"} />
      <span className="text-text-muted">{label}</span>
      <motion.span
        key={String(value)}
        initial={reduce ? false : { y: -5, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
        className={`font-semibold tabular-nums ${alert ? "text-warning" : "text-text-primary"}`}
      >
        {value}
      </motion.span>
      {live && !reduce && (
        <motion.span
          aria-hidden
          className="h-1.5 w-1.5 rounded-full bg-teal"
          animate={{ opacity: [1, 0.3, 1], scale: [1, 0.8, 1] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
    </span>
  );
}

export default function AgentActionsPage() {
  const { run, logs, running, start, loadLatest } = useAgentRun();
  const hydrated = useRef(false);
  const [actions, setActions] = useState<ActionItem[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [audit, setAudit] = useState<any[]>([]);
  const [faults, setFaults] = useState(0);
  const [busyApproval, setBusyApproval] = useState<string | null>(null);

  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [chatRunEvent, setChatRunEvent] = useState<ChatRunEvent | null>(null);

  const triggerRun = async (action: "run_optimization" | "run_prediction") => {
    const starter = action === "run_optimization"
      ? () => api.runOptimization(scenario, sessionId)
      : () => api.runPrediction(scenario, sessionId);
    try {
      const result = await start(starter);
      const targetSessionId = result.session_id || sessionId;
      if (!targetSessionId) return;
      setChatRunEvent({ runId: result.run_id, action, sessionId: targetSessionId });
      if (targetSessionId !== sessionId) onSessionId(targetSessionId);
      else loadSessions();
    } catch {
      // useAgentRun leaves the previous run intact; the next click can retry.
    }
  };
  const loadSessions = useCallback(() => {
    api.chatSessions().then(setSessions).catch(() => null);
  }, []);

  const refresh = useCallback(() => {
    api.actions().then(setActions).catch(() => null);
    api.approvals().then(setApprovals).catch(() => null);
    api.auditLog().then(setAudit).catch(() => null);
    api.alertsSummary().then((s) => setFaults(s.total ?? 0)).catch(() => null);
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

  // A finished run can add actions/approvals and change the session summary.
  useEffect(() => {
    if (!running && run) { refresh(); loadSessions(); }
  }, [running, run, refresh, loadSessions]);

  const scenario = { horizon_minutes: 60, allow_auto_action: true };

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

  const onSessionId = (id: string) => { setSessionId(id); loadSessions(); };
  const removeSession = async (id: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== id)); // optimistic
    if (sessionId === id) setSessionId(null);
    await api.deleteSession(id).catch(() => null);
    loadSessions();
  };
  const activeSession = sessions.find((s) => s.id === sessionId) || null;
  const pending = approvals.length;

  return (
    <div className="pb-4">
      <PageHeader
        title="Agents & Actions"
        actions={
          <>
            <button className="btn-secondary" disabled={running}
                    onClick={() => triggerRun("run_prediction")}>
              <TrendingUp size={15} /> Run Prediction
            </button>
            <button className="btn-primary" disabled={running}
                    onClick={() => triggerRun("run_optimization")}>
              {running ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
              Run Optimization
            </button>
          </>
        }
      />

      {/* glance status: plain inline, grouped by space (no cards, no dot spam) */}
      <div className="mb-4 flex flex-wrap items-center gap-x-8 gap-y-1.5 text-[12.5px]">
        <Stat icon={Bot} label="Agent" value={running ? "running" : "idle"} alert={running} live={running} />
        <Stat icon={ClipboardCheck} label="Awaiting approval" value={pending} alert={pending > 0} />
        <Stat icon={AlertTriangle} label="Open faults" value={faults} alert={faults > 0} />
      </div>

      {/* three purposeful zones: sessions, conversation, actions */}
      <div className="grid gap-4 lg:grid-cols-[208px_1fr_384px]">
        {/* sessions */}
        <aside className="card-elevated flex h-[200px] flex-col p-0 lg:h-[640px]">
          <div className="flex items-center justify-between border-b border-border/70 px-3.5 py-3">
            <span className="text-[13px] font-semibold tracking-tight">Sessions</span>
            <button onClick={() => setSessionId(null)} title="New session"
                    className="flex items-center gap-1 rounded-lg px-2 py-1 text-[12px] font-medium text-teal hover:bg-teal-soft">
              <Plus size={14} /> New
            </button>
          </div>
          <div className="flex-1 space-y-0.5 overflow-y-auto px-2 py-2">
            {sessions.length === 0 && (
              <p className="px-2 py-3 text-[12px] leading-relaxed text-text-muted">
                No conversations yet. Ask the agent anything about the building.
              </p>
            )}
            {sessions.map((s) => (
              <div key={s.id} className="group relative">
                <button onClick={() => setSessionId(s.id)}
                        className={`block w-full rounded-lg px-2.5 py-2 pr-8 text-left transition hover:bg-surface-muted
                          ${s.id === sessionId ? "bg-teal-soft" : ""}`}>
                  <p className={`truncate text-[12.5px] ${s.id === sessionId ? "font-medium text-teal" : "text-text-secondary"}`}>
                    {s.first_message ? displayPromptInEnglish(s.first_message) : "New conversation"}
                  </p>
                  <p className="mt-0.5 text-[11px] text-text-muted">{s.n_messages} messages</p>
                </button>
                <button onClick={() => removeSession(s.id)} title="Delete conversation"
                        className="absolute right-1.5 top-1.5 hidden rounded-md p-1.5 text-text-muted transition hover:bg-white hover:text-danger group-hover:block">
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        </aside>

        {/* conversation (hero): chat with agent run traces streaming inline */}
        <section className="card-elevated flex h-[560px] flex-col p-0 lg:h-[640px]">
          <div className="flex items-center gap-2.5 border-b border-border/70 px-4 py-3.5">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-teal text-white shadow-[0_4px_12px_-4px_rgba(13,148,136,0.5)]">
              <Bot size={16} />
            </span>
            <div className="min-w-0">
              <p className="truncate text-[13.5px] font-semibold tracking-tight">
                {activeSession?.first_message
                  ? displayPromptInEnglish(activeSession.first_message)
                  : "Building agent"}
              </p>
              <p className="text-[11px] text-text-muted">
                {running ? "reasoning live…"
                  : activeSession ? `${activeSession.n_messages} messages`
                  : "Chat, or run a workflow - the trace streams in here"}
              </p>
            </div>
          </div>
          <ChatThread sessionId={sessionId} onSessionId={onSessionId}
            runEvent={chatRunEvent} />
        </section>

        {/* actions */}
        <aside className="flex h-[560px] flex-col lg:h-[640px]">
          <ActionQueue
            actions={actions}
            approvals={approvals}
            onApprove={(id) => decide(id, true)}
            onReject={(id) => decide(id, false)}
            busyId={busyApproval}
          />
        </aside>
      </div>

      {/* advanced run internals, tucked away so the default view stays calm */}
      <details className="group mt-3">
        <summary className="flex w-fit cursor-pointer list-none items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium text-text-secondary transition hover:bg-surface-muted">
          <TrendingUp size={14} className="text-text-muted transition group-open:rotate-90" />
          Run details
          <span className="text-[11px] text-text-muted">timeline, prediction, policy, audit</span>
        </summary>
        <div className="mt-3 space-y-3">
          <AgentRunTimeline run={run} logs={logs} running={running} />
          <div className="grid gap-3 lg:grid-cols-3">
            <PredictionPanel run={run} />
            <PolicySummaryCard />
            <AuditTable rows={audit.slice(0, 30)} />
          </div>
        </div>
      </details>
    </div>
  );
}
