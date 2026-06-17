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

export interface ChatResponse {
  run_id: string;
  answer: string;
  intent?: string;
  related_entities?: { entity_key: string; entity_type: string; label: string }[];
  viewer_updates?: ViewerUpdate[];
  suggested_buttons?: string[];
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
