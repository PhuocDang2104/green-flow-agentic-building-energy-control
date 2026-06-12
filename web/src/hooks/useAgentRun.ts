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

  useEffect(() => stopPolling, [stopPolling]);

  return { runId, run, logs, running, start, watch };
}
