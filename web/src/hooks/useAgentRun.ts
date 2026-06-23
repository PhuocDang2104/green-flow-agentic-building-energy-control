"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { AgentLog, AgentRun } from "@/lib/types";
import { useAppStore } from "@/stores/appStore";

/** Start agent runs and poll logs/status until completion. */
export function useAgentRun() {
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [running, setRunning] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const setViewerUpdates = useAppStore((s) => s.setViewerUpdates);
  const setActiveAgentRunId = useAppStore((s) => s.setActiveAgentRunId);

  const stopPolling = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
  }, []);

  const watch = useCallback((id: string) => {
    setRunId(id);
    setActiveAgentRunId(id);
    setRunning(true);
    setLogs([]);
    setRun(null);
    stopPolling();
    timerRef.current = setInterval(async () => {
      try {
        const [r, l] = await Promise.all([api.agentRun(id), api.agentRunLogs(id)]);
        setRun(r);
        setLogs(l);
        if (r.status !== "running") {
          setRunning(false);
          stopPolling();
          if (r.viewer_updates?.length) setViewerUpdates(r.viewer_updates);
        }
      } catch {
        /* keep polling */
      }
    }, 1200);
  }, [setActiveAgentRunId, setViewerUpdates, stopPolling]);

  const start = useCallback(async (
    starter: () => Promise<{ run_id: string }>,
  ) => {
    const { run_id } = await starter();
    watch(run_id);
    return run_id;
  }, [watch]);

  /**
   * Show an existing run's timeline read-only (history). If it's still running,
   * attach the live poller instead. Unlike `watch`, this does NOT replay the
   * run's viewer_updates, so loading a past run never recolors the 3D twin.
   */
  const load = useCallback(async (id: string) => {
    try {
      const r = await api.agentRun(id);
      if (r.status === "running") { watch(id); return; }
      const l = await api.agentRunLogs(id);
      setRunId(id);
      setActiveAgentRunId(id);
      setRun(r);
      setLogs(l);
      setRunning(false);
    } catch {
      /* ignore — leave the empty state */
    }
  }, [watch, setActiveAgentRunId]);

  /** Hydrate the timeline with the most recent run so the tab is never blank. */
  const loadLatest = useCallback(async () => {
    try {
      const runs = await api.agentRuns(); // newest first
      if (runs.length) await load(runs[0].id);
    } catch {
      /* ignore */
    }
  }, [load]);

  useEffect(() => stopPolling, [stopPolling]);

  return { runId, run, logs, running, start, watch, load, loadLatest };
}
