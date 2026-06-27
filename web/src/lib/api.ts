// Typed API client. All paths are same-origin (/api/...) — Next dev rewrites
// and Caddy in production both route them to the FastAPI backend.

import type {
  ActionItem, AgentLog, AgentRun, AgentRunStart, Alert, Approval, Building, ChatMessageRow,
  ChatQueryResponse, ChatSessionSummary, ComparisonKpi, Device,
  HealthScore, Kpis, ReplayStatus, Report, SimulationRun, ValidationResult, Zone,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} -> ${res.status}`);
  return res.json();
}

export const api = {
  // self-hosted voice (faster-whisper STT + Piper TTS)
  transcribe: async (blob: Blob): Promise<{ text: string }> => {
    const fd = new FormData();
    fd.append("file", blob, "audio.webm");
    const res = await fetch(`${BASE}/voice/transcribe`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(`transcribe -> ${res.status}`);
    return res.json();
  },
  speak: async (text: string): Promise<Blob> => {
    const res = await fetch(`${BASE}/voice/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error(`speak -> ${res.status}`);
    return res.blob();
  },

  buildings: () => get<Building[]>("/buildings"),
  kpis: () => get<Kpis>("/kpi/current"),
  healthScore: () => get<HealthScore>("/kpi/health-score"),
  zones: () => get<Zone[]>("/zones"),
  devices: (zoneId?: string) =>
    get<Device[]>(`/devices${zoneId ? `?zone_id=${zoneId}` : ""}`),
  entity: (key: string) => get<any>(`/entities/${key}`),
  entityNeighbors: (key: string) => get<any>(`/entities/${key}/neighbors`),
  zoneHistory: (zoneRef: string, hours = 24) =>
    get<any[]>(`/timeseries?zone=${zoneRef}&hours=${hours}`),
  buildingTimeseries: (hours = 24) => get<any[]>(`/timeseries/building?hours=${hours}`),
  latestState: () => get<any>("/state/latest"),

  // agent
  runOptimization: (scenario_config = {}, session_id?: string | null) =>
    post<AgentRunStart>("/agent/run-optimization", { scenario_config, session_id }),
  runPrediction: (scenario_config = {}, session_id?: string | null) =>
    post<AgentRunStart>("/agent/predict", { scenario_config, session_id }),
  peakStrategy: (scenario_config = {}) =>
    post<{ run_id: string }>("/agent/peak-strategy", { scenario_config }),
  compareBaseline: () => post<{ run_id: string }>("/agent/compare-baseline-optimized"),
  reportBuildingSemantic: () =>
    post<{ run_id: string }>("/agent/report/building-semantic"),
  reportHvacElec: () => post<{ run_id: string }>("/agent/report/hvac-elec"),
  agentRuns: () => get<AgentRun[]>("/agent/runs"),
  agentRun: (id: string) => get<AgentRun>(`/agent/runs/${id}`),
  agentRunLogs: (id: string) => get<AgentLog[]>(`/agent/runs/${id}/logs`),

  // data-query chatbot (RAG + SQL function-calling, persisted conversation)
  chatQuery: (message: string, session_id?: string | null) =>
    post<ChatQueryResponse>("/chat", { message, session_id: session_id || undefined }),
  modelInfo: () => get<any>("/ml/model-info"),
  chatSessions: () => get<ChatSessionSummary[]>("/chat/sessions"),
  deleteSession: async (id: string): Promise<void> => {
    const res = await fetch(`${BASE}/chat/sessions/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`delete session -> ${res.status}`);
  },
  chatSessionMessages: (sessionId: string) =>
    get<ChatMessageRow[]>(`/chat/sessions/${sessionId}/messages`),

  // replay streaming (live demo mode)
  replayStream: (on: boolean, speed = 900) =>
    post<ReplayStatus>("/replay/stream", { on, speed }),
  replayStatus: () => get<ReplayStatus>("/replay/status"),

  // actions / approvals
  actions: (status?: string) =>
    get<ActionItem[]>(`/actions${status ? `?status=${status}` : ""}`),
  approvals: (status = "pending", runId?: string) =>
    get<Approval[]>(`/approvals?status=${status}${runId ? `&run_id=${encodeURIComponent(runId)}` : ""}`),
  approve: (id: string, note = "") =>
    post<any>(`/approvals/${id}/approve`, { decided_by: "demo_user", note }),
  rejectApproval: (id: string, note = "") =>
    post<any>(`/approvals/${id}/reject`, { decided_by: "demo_user", note }),
  auditLog: () => get<any[]>("/audit-log"),
  policyConfig: () => get<any>("/policy-config"),

  // alerts / fault detection & diagnostics (FDD)
  alerts: (status = "open") => get<Alert[]>(`/alerts?status=${status}`),
  alertsSummary: () => get<{ critical: number; warning: number; info: number; total: number }>("/alerts/summary"),
  acknowledgeAlert: (id: string) => post(`/alerts/${id}/acknowledge`),
  scanAnomalies: () => post<{ alerts_written: number }>("/agent/scan-anomalies"),

  // simulations
  simulations: () => get<SimulationRun[]>("/simulations"),
  latestComparison: () => get<any>("/simulations/compare/latest"),
  comparisonSeries: (metric = "total_power_kw") =>
    get<{ metric: string; kpi: ComparisonKpi; series: any[] }>(
      `/simulations/compare/series?metric=${metric}`),
  runSeries: (runId: string, metric = "total_power_kw") =>
    get<{ timestamp: string; value: number }[]>(
      `/simulations/${runId}/series?metric=${metric}`),
  createScenario: (payload: {
    apply_ai: boolean; strategy?: string; horizon_minutes?: number; label?: string;
  }) => post<{ run_id: string; status: string; mode: string }>("/simulations/scenario", payload),
  deleteSimulation: async (id: string): Promise<void> => {
    const res = await fetch(`${BASE}/simulations/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`delete simulation -> ${res.status}`);
  },
  // period (campaign) what-if: building WITHOUT AI vs WITH a fixed policy
  campaign: (payload: {
    setpoint_delta: number; peak_start?: number; peak_end?: number;
    date_from?: string; date_to?: string;
  }) => post<{
    policy: { setpoint_delta_c: number; peak_window: string; engine: string };
    kpi: {
      baseline_kwh: number; optimized_kwh: number; saving_kwh: number;
      saving_percent: number; cost_saving_vnd: number; peak_reduction_kw: number;
      comfort_violation_delta_min: number; co2_avoided_kg: number; days: number;
    };
    daily: { date: string; baseline_kwh: number; optimized_kwh: number;
             peak_baseline_kw: number; peak_optimized_kw: number }[];
  }>("/simulations/campaign", payload),
  simulateRecommended: () =>
    post<{ run_id: string }>("/simulation/simulate-recommended-actions"),
  validateBaseline: (isWeekend?: boolean) =>
    get<ValidationResult>(`/simulations/validate-baseline${
      isWeekend === undefined ? "" : `?is_weekend=${isWeekend}`}`),

  // reports / scenarios
  reports: () => get<Report[]>("/reports"),
  scenarios: () => get<any[]>("/scenarios"),

  // climate scenario (El Niño heat-stress what-if)
  saveScenario: (payload: any) => post<any>("/scenarios/save", payload),
  runIdfSimulation: (payload: any) => post<any>("/simulations/run-idf", payload),

  // electrical-distribution knowledge graph (file-backed; needs the pipeline run)
  elecOverview: () => get<any>("/electrical/overview"),
  elecScene: (loads = true, maxLights = 800) =>
    get<any>(`/electrical/scene?loads=${loads}&max_lights=${maxLights}`),
  elecBoards: () => get<{ count: number; boards: any[] }>("/electrical/boards"),
  elecCircuits: () => get<{ count: number; circuits: any[] }>("/electrical/circuits"),
  elecPhaseBalance: () => get<{ count: number; phase_balance: any[] }>("/electrical/phase-balance"),
  elecBoard: (id: string) => get<any>(`/electrical/boards/${id}`),
  elecBoardTimeseries: (id: string, freq: "daily" | "monthly" = "daily") =>
    get<{ board_id: string; freq: string; points: any[] }>(
      `/electrical/boards/${id}/timeseries?freq=${freq}`),
  elecZone: (zoneId: string) => get<any>(`/electrical/zones/${zoneId}/electrical`),
  elecFloor: (floorId: string) => get<any>(`/electrical/floors/${floorId}`),
  elecRagAnswer: (question: string) =>
    get<any>(`/graph/rag/answer?question=${encodeURIComponent(question)}`),
};

// Resolve a stored media/report path to an absolute URL against the API origin.
// `/media/...` is under the API's /api prefix; legacy `/storage/...` is at the
// API root. Works same-origin (BASE="/api") and cross-origin on Vercel
// (BASE="https://host/api").
const API_ORIGIN = BASE.replace(/\/api\/?$/, "");
export function mediaUrl(path: string | null | undefined): string {
  if (!path) return "";
  if (/^https?:\/\//.test(path)) return path;
  if (path.startsWith("/media")) return `${BASE}${path}`;
  return `${API_ORIGIN}${path.startsWith("/") ? path : "/" + path}`;
}

export function wsUrl(buildingId: string): string {
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  // next dev runs on :3000 without ws proxying; talk to the API directly
  const host = window.location.port === "3000"
    ? `${window.location.hostname}:8000`
    : window.location.host;
  return `${proto}://${host}/ws/building/${buildingId}/state`;
}
