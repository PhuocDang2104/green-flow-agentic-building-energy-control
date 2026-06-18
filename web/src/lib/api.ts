// Typed API client. All paths are same-origin (/api/...) — Next dev rewrites
// and Caddy in production both route them to the FastAPI backend.

import type {
  ActionItem, AgentLog, AgentRun, Approval, Building, ChatMessageRow,
  ChatQueryResponse, ChatResponse, ChatSessionSummary, ComparisonKpi, Device,
  Kpis, Report, SimulationRun, ValidationResult, Zone,
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
  buildings: () => get<Building[]>("/buildings"),
  kpis: () => get<Kpis>("/kpi/current"),
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
  runOptimization: (scenario_config = {}) =>
    post<{ run_id: string }>("/agent/run-optimization", { scenario_config }),
  runPrediction: (scenario_config = {}) =>
    post<{ run_id: string }>("/agent/predict", { scenario_config }),
  peakStrategy: (scenario_config = {}) =>
    post<{ run_id: string }>("/agent/peak-strategy", { scenario_config }),
  compareBaseline: () => post<{ run_id: string }>("/agent/compare-baseline-optimized"),
  reportBuildingSemantic: () =>
    post<{ run_id: string }>("/agent/report/building-semantic"),
  reportHvacElec: () => post<{ run_id: string }>("/agent/report/hvac-elec"),
  chat: (message: string, session_id?: string) =>
    post<ChatResponse>("/agent/chat", { message, session_id }),
  agentRuns: () => get<AgentRun[]>("/agent/runs"),
  agentRun: (id: string) => get<AgentRun>(`/agent/runs/${id}`),
  agentRunLogs: (id: string) => get<AgentLog[]>(`/agent/runs/${id}/logs`),

  // data-query chatbot (RAG + SQL function-calling, persisted conversation)
  chatQuery: (message: string, session_id?: string | null) =>
    post<ChatQueryResponse>("/chat", { message, session_id: session_id || undefined }),
  chatSessions: () => get<ChatSessionSummary[]>("/chat/sessions"),
  chatSessionMessages: (sessionId: string) =>
    get<ChatMessageRow[]>(`/chat/sessions/${sessionId}/messages`),

  // actions / approvals
  actions: (status?: string) =>
    get<ActionItem[]>(`/actions${status ? `?status=${status}` : ""}`),
  approvals: (status = "pending") => get<Approval[]>(`/approvals?status=${status}`),
  approve: (id: string, note = "") =>
    post<any>(`/approvals/${id}/approve`, { decided_by: "demo_user", note }),
  rejectApproval: (id: string, note = "") =>
    post<any>(`/approvals/${id}/reject`, { decided_by: "demo_user", note }),
  auditLog: () => get<any[]>("/audit-log"),
  policyConfig: () => get<any>("/policy-config"),

  // simulations
  simulations: () => get<SimulationRun[]>("/simulations"),
  latestComparison: () => get<any>("/simulations/compare/latest"),
  comparisonSeries: (metric = "total_power_kw") =>
    get<{ metric: string; kpi: ComparisonKpi; series: any[] }>(
      `/simulations/compare/series?metric=${metric}`),
  simulateRecommended: () =>
    post<{ run_id: string }>("/simulation/simulate-recommended-actions"),
  validateBaseline: (isWeekend?: boolean) =>
    get<ValidationResult>(`/simulations/validate-baseline${
      isWeekend === undefined ? "" : `?is_weekend=${isWeekend}`}`),

  // reports / scenarios
  reports: () => get<Report[]>("/reports"),
  scenarios: () => get<any[]>("/scenarios"),
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
