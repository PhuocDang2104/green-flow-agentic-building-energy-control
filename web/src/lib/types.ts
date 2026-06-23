// Shared API types (mirrors backend schemas)

export interface Building {
  id: string;
  name: string;
  location_name?: string;
  building_type?: string;
}

export interface ZoneState {
  timestamp?: string;
  occupancy_count?: number;
  occupancy_state?: string;
  occupancy_confidence?: number;
  temperature_c?: number;
  humidity_pct?: number;
  co2_ppm?: number;
  hvac_power_kw?: number;
  lighting_power_kw?: number;
  plug_power_kw?: number;
  total_power_kw?: number;
  setpoint_c?: number;
  comfort_risk?: string;
  peak_risk?: string;
  anomaly_label?: string | null;
}

export interface Zone {
  id: string;
  name: string;
  entity_key: string;
  room_type: string;
  area_m2?: number;
  volume_m3?: number;
  floor_name?: string;
  latest_state?: ZoneState | null;
}

export interface Device {
  id: string;
  name: string;
  entity_key: string;
  device_type: string;
  device_subtype?: string;
  tag?: string;
  controllable: boolean;
  risk_level?: string;
  status?: string;
  nominal_power_kw?: number;
  zone_key?: string | null;
  zone_name?: string | null;
}

export interface Camera {
  id: string;
  name: string;
  video_source?: string | null;
  privacy_mode?: string;
  zone_key?: string | null;
}

export interface Kpis {
  timestamp?: string;
  total_kw?: number;
  occupancy?: number;
  occ_conf?: number;
  comfort_watch?: number;
  comfort_high?: number;
  peak_high?: number;
  anomalies?: number;
  kwh?: number;
  cost?: number;
  executed?: number;
  pending?: number;
}

export interface HealthDimension {
  key: string;
  label: string;
  score: number;
  weight: number;
  detail: string;
}

export interface HealthScore {
  timestamp?: string;
  score: number;
  grade: "Excellent" | "Good" | "Fair" | "Poor";
  color: "success" | "teal" | "warning" | "danger";
  zones: number;
  dimensions: HealthDimension[];
}

export interface AgentLog {
  step: number;
  node: string;
  status: "running" | "completed" | "warning" | "failed";
  message: string;
  duration_ms?: number;
  output_summary?: Record<string, unknown>;
  created_at?: string;
}

export interface AgentRun {
  id: string;
  entrypoint: string;
  button_action?: string;
  user_query?: string;
  intent?: string;
  status: string;
  started_at: string;
  finished_at?: string;
  final_answer?: string;
  dashboard_cards?: DashboardCard[];
  viewer_updates?: ViewerUpdate[];
  state_json?: Record<string, any>;
}

export interface DashboardCard {
  title: string;
  value: string;
  subtitle?: string;
  status?: "success" | "warning" | "danger" | "info";
}

export interface ViewerUpdate {
  entity_id: string;
  style: {
    color?: string;
    opacity?: number;
    label?: string;
    outline?: boolean;
  };
}

export interface ActionItem {
  id: string;
  action_type: string;
  status: string;
  reason?: string;
  decision_mode?: string;
  policy_decision?: string;
  policy_reasons?: string[];
  expected_saving_kwh?: number;
  expected_peak_reduction_kw?: number;
  comfort_risk_after?: number;
  confidence?: number;
  requested_at: string;
  targets?: { target_type: string; target_id: string; parameters?: any }[];
}

export interface Approval {
  approval_id: string;
  action_id: string;
  status: string;
  action_type: string;
  reason?: string;
  expected_saving_kwh?: number;
  expected_peak_reduction_kw?: number;
  comfort_risk_after?: number;
  policy_reasons?: string[];
  requested_at: string;
}

export interface SimulationRun {
  id: string;
  baseline_label?: string;
  run_kind: string;
  engine: string;
  status: string;
  started_at: string;
  actions_json?: any[];
  totals?: {
    energy_kwh: number;
    hvac_kwh: number;
    lighting_kwh: number;
    peak_demand_kw: number;
    comfort_violation_minutes: number;
  };
}

export interface ComparisonKpi {
  baseline_kwh: number;
  optimized_kwh: number;
  saving_kwh: number;
  saving_percent: number;
  cost_saving_vnd: number;
  peak_reduction_kw: number;
  comfort_violation_delta_min: number;
  co2_avoided_kg: number;
  peak_window_baseline_kw?: number;
  peak_window_optimized_kw?: number;
}

export interface ValidationResult {
  date: string;
  is_weekend: boolean;
  engine: string;
  real_kwh: number;
  sim_kwh: number;
  mape_pct: number | null;
  rmse_kw: number;
  verdict: "well calibrated" | "acceptable, minor drift" | "needs recalibration";
  peak_real_kw: number | null;
  peak_real_time: string | null;
  peak_sim_kw: number | null;
  peak_sim_time: string | null;
  series: { minutes: number; time: string; real_kw: number; sim_kw: number }[];
  zones: { zone_key: string; zone_name: string; real_kwh: number; sim_kwh: number;
           error_pct: number | null }[];
}

export interface ChatResponse {
  run_id: string;
  answer: string;
  intent?: string;
  related_entities?: { entity_key: string; entity_type: string; label: string }[];
  viewer_updates?: ViewerUpdate[];
  suggested_buttons?: string[];
}

export interface ChatQueryResponse {
  session_id: string;
  answer: string;
  tools_used?: { name: string; args: Record<string, unknown>; result?: any }[];
  sources?: string[];
}

export interface ChatSessionSummary {
  id: string;
  created_at: string;
  first_message: string | null;
  n_messages: number;
}

export interface ChatMessageRow {
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  tool_calls?: { name: string; args: Record<string, unknown>; result?: any }[];
  created_at: string;
}

export interface Alert {
  id: string;
  alert_type: string;
  severity: "critical" | "warning" | "info";
  message: string;
  created_at: string;
  resolved_at?: string | null;
  zone_key?: string | null;
  zone_name?: string | null;
  room_type?: string | null;
  device_name?: string | null;
}

export interface Report {
  id: string;
  report_type: string;
  title: string;
  status: string;
  pdf_url?: string | null;
  created_at: string;
}

export interface ViewerManifestAsset {
  asset_id: string;
  layer: string;
  model_id: string;
  src: string;
  glb_src?: string;
  metadata_src: string;
  default_visible: boolean;
  pickable?: boolean;
}

export interface ViewerManifest {
  building_key: string;
  building_name: string;
  geometry_format: string;
  geometry_json_src: string;
  object_map_src: string;
  assets: ViewerManifestAsset[];
}

export interface ObjectMapEntry {
  xeokit_object_id: string;
  entity_key: string;
  entity_type: string;
  zone_key?: string | null;
  floor_key?: string;
  layer: string;
  name: string;
  live?: boolean;
  room_type?: string | null;
}
