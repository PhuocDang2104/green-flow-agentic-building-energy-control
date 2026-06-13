-- GreenFlow MVP database schema
-- PostgreSQL 15+ with pgvector
-- Base: docs/project-readme/DATABASE_SCHEMA.sql
-- Extended with: entity_relations, geometry_assets, mesh_entity_map,
-- agent_runs, agent_logs, approval_requests, scenarios, scenario_kpi,
-- reports, artifacts.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- Core reference tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS buildings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  location_name text,
  timezone text NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
  building_type text,
  source_dataset text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS floors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  floor_index integer NOT NULL,
  name text NOT NULL,
  elevation_m numeric,
  raw_ifc_guid text
);

CREATE UNIQUE INDEX IF NOT EXISTS floors_building_index_uniq
  ON floors(building_id, floor_index);

CREATE TABLE IF NOT EXISTS zones (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  floor_id uuid REFERENCES floors(id) ON DELETE SET NULL,
  name text NOT NULL,
  entity_key text,                     -- stable entity_id used by 3D viewer / agent
  room_type text,
  area_m2 numeric,
  volume_m3 numeric,
  comfort_profile text,
  risk_level text DEFAULT 'normal',
  raw_ifc_guid text,
  source_space_name text
);

CREATE INDEX IF NOT EXISTS zones_building_floor_idx ON zones(building_id, floor_id);
CREATE INDEX IF NOT EXISTS zones_name_idx ON zones(name);
CREATE UNIQUE INDEX IF NOT EXISTS zones_entity_key_uniq ON zones(building_id, entity_key);

CREATE TABLE IF NOT EXISTS rooms (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  zone_id uuid NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
  name text NOT NULL,
  capacity integer,
  usage_type text,
  raw_ifc_guid text
);

CREATE TABLE IF NOT EXISTS devices (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  floor_id uuid REFERENCES floors(id) ON DELETE SET NULL,
  zone_id uuid REFERENCES zones(id) ON DELETE SET NULL,
  device_type text NOT NULL,
  device_subtype text,
  name text NOT NULL,
  entity_key text,
  tag text,
  controllable boolean NOT NULL DEFAULT false,
  risk_level text DEFAULT 'normal',
  status text DEFAULT 'unknown',
  nominal_capacity numeric,
  nominal_power_kw numeric,
  raw_ifc_guid text,
  raw_storey_guid text
);

CREATE INDEX IF NOT EXISTS devices_building_zone_idx ON devices(building_id, zone_id);
CREATE INDEX IF NOT EXISTS devices_type_idx ON devices(device_type);
CREATE INDEX IF NOT EXISTS devices_controllable_idx ON devices(controllable);
CREATE UNIQUE INDEX IF NOT EXISTS devices_entity_key_uniq ON devices(building_id, entity_key);

CREATE TABLE IF NOT EXISTS device_systems (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id uuid NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  system_guid text,
  system_name text,
  system_type text,
  raw_ifc_guid text
);

CREATE INDEX IF NOT EXISTS device_systems_device_idx ON device_systems(device_id);
CREATE INDEX IF NOT EXISTS device_systems_system_name_idx ON device_systems(system_name);

CREATE TABLE IF NOT EXISTS meters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  floor_id uuid REFERENCES floors(id) ON DELETE SET NULL,
  zone_id uuid REFERENCES zones(id) ON DELETE SET NULL,
  meter_type text,
  unit text,
  name text NOT NULL,
  raw_ifc_guid text
);

CREATE TABLE IF NOT EXISTS cameras (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  floor_id uuid REFERENCES floors(id) ON DELETE SET NULL,
  zone_id uuid REFERENCES zones(id) ON DELETE SET NULL,
  name text NOT NULL,
  video_source text,
  privacy_mode text DEFAULT 'count_only',
  raw_ifc_guid text
);

CREATE TABLE IF NOT EXISTS tariff_rules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  metric_type text NOT NULL,
  unit_price numeric NOT NULL,
  currency text NOT NULL DEFAULT 'VND',
  peak_start time,
  peak_end time,
  weekday_mask integer,
  effective_from date NOT NULL,
  effective_to date
);

-- ---------------------------------------------------------------------------
-- Graph / 3D mapping tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS entity_relations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  src_entity_type text NOT NULL,
  src_entity_id uuid NOT NULL,
  relation_type text NOT NULL,
  dst_entity_type text NOT NULL,
  dst_entity_id uuid NOT NULL,
  confidence numeric DEFAULT 1.0,
  method text,
  properties jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS entity_relations_src_idx
  ON entity_relations(building_id, src_entity_id, relation_type);
CREATE INDEX IF NOT EXISTS entity_relations_dst_idx
  ON entity_relations(building_id, dst_entity_id, relation_type);

CREATE TABLE IF NOT EXISTS geometry_assets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  layer text NOT NULL,
  asset_url text NOT NULL,
  metadata_url text,
  asset_type text NOT NULL DEFAULT 'xkt',
  default_visible boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mesh_entity_map (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id uuid REFERENCES geometry_assets(id) ON DELETE CASCADE,
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  mesh_id text NOT NULL,                -- xeokit object id
  entity_type text NOT NULL,
  entity_id uuid,
  entity_key text,
  raw_ifc_guid text,
  floor_id uuid REFERENCES floors(id) ON DELETE SET NULL,
  layer text,
  properties jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS mesh_entity_map_building_idx
  ON mesh_entity_map(building_id, mesh_id);
CREATE INDEX IF NOT EXISTS mesh_entity_map_entity_idx
  ON mesh_entity_map(entity_id);

-- ---------------------------------------------------------------------------
-- Time-series tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS telemetry_zone_15m (
  timestamp timestamptz NOT NULL,
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  floor_id uuid REFERENCES floors(id) ON DELETE SET NULL,
  zone_id uuid NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
  occupancy_count integer NOT NULL DEFAULT 0,
  occupancy_state text NOT NULL DEFAULT 'empty',
  occupancy_confidence numeric,
  temperature_c numeric,
  humidity_pct numeric,
  co2_ppm numeric,
  hvac_power_kw numeric NOT NULL DEFAULT 0,
  lighting_power_kw numeric NOT NULL DEFAULT 0,
  plug_power_kw numeric,
  total_power_kw numeric NOT NULL DEFAULT 0,
  energy_kwh numeric NOT NULL DEFAULT 0,
  cost_vnd numeric NOT NULL DEFAULT 0,
  setpoint_c numeric,
  comfort_risk text,
  peak_risk text,
  anomaly_label text,
  scenario_id text,
  PRIMARY KEY (timestamp, zone_id)
);

CREATE INDEX IF NOT EXISTS telemetry_zone_building_ts_idx
  ON telemetry_zone_15m(building_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS telemetry_zone_floor_ts_idx
  ON telemetry_zone_15m(floor_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS telemetry_device_15m (
  timestamp timestamptz NOT NULL,
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  floor_id uuid REFERENCES floors(id) ON DELETE SET NULL,
  zone_id uuid REFERENCES zones(id) ON DELETE SET NULL,
  device_id uuid NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  device_type text NOT NULL,
  status text NOT NULL DEFAULT 'unknown',
  mode text,
  setpoint_c numeric,
  power_kw numeric NOT NULL DEFAULT 0,
  energy_kwh numeric NOT NULL DEFAULT 0,
  runtime_minutes integer NOT NULL DEFAULT 0,
  fault_state text,
  command_source text,
  scenario_id text,
  PRIMARY KEY (timestamp, device_id)
);

CREATE INDEX IF NOT EXISTS telemetry_device_building_ts_idx
  ON telemetry_device_15m(building_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS telemetry_device_zone_ts_idx
  ON telemetry_device_15m(zone_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS occupancy_zone_15m (
  timestamp timestamptz NOT NULL,
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  floor_id uuid REFERENCES floors(id) ON DELETE SET NULL,
  zone_id uuid NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
  person_count integer NOT NULL DEFAULT 0,
  occupied boolean NOT NULL DEFAULT false,
  confidence numeric,
  source_type text,
  PRIMARY KEY (timestamp, zone_id)
);

CREATE TABLE IF NOT EXISTS weather_15m (
  timestamp timestamptz NOT NULL,
  location_name text NOT NULL,
  outdoor_temp_c numeric,
  humidity_pct numeric,
  wind_speed_mps numeric,
  cloud_cover_pct numeric,
  precipitation_mm numeric,
  solar_w_m2 numeric,
  forecast_horizon_min integer,
  PRIMARY KEY (timestamp, location_name)
);

-- ---------------------------------------------------------------------------
-- Action / simulation / forecast
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS actions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  agent_run_id uuid,
  requested_at timestamptz NOT NULL DEFAULT now(),
  decision_mode text NOT NULL DEFAULT 'recommendation',
  action_type text NOT NULL,
  status text NOT NULL DEFAULT 'proposed',   -- proposed|pending_approval|approved|executed|rejected|blocked
  reason text,
  confidence numeric,
  expected_saving_kwh numeric,
  expected_peak_reduction_kw numeric,
  comfort_risk_after numeric,
  policy_decision text,
  policy_reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  parameters_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by text NOT NULL DEFAULT 'system',
  simulation_run_id uuid
);

CREATE INDEX IF NOT EXISTS actions_building_requested_idx
  ON actions(building_id, requested_at DESC);

CREATE TABLE IF NOT EXISTS action_targets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_id uuid NOT NULL REFERENCES actions(id) ON DELETE CASCADE,
  target_type text NOT NULL,
  target_id uuid NOT NULL,
  parameters_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS action_targets_action_idx ON action_targets(action_id);

CREATE TABLE IF NOT EXISTS approval_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_id uuid NOT NULL REFERENCES actions(id) ON DELETE CASCADE,
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'pending',    -- pending|approved|rejected|modified
  requested_at timestamptz NOT NULL DEFAULT now(),
  decided_at timestamptz,
  decided_by text,
  decision_note text,
  payload_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS approval_requests_building_idx
  ON approval_requests(building_id, status, requested_at DESC);

CREATE TABLE IF NOT EXISTS scenarios (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  name text NOT NULL,
  scenario_type text NOT NULL DEFAULT 'normal',  -- normal|heatwave|after_hours|high_occupancy|peak_strategy
  description text,
  config_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS simulation_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  baseline_label text,
  run_kind text NOT NULL DEFAULT 'baseline',     -- baseline|agent|what_if|peak_strategy
  engine text NOT NULL DEFAULT 'synthetic',      -- energyplus|synthetic|rule_quick_estimate
  scenario_id uuid REFERENCES scenarios(id) ON DELETE SET NULL,
  actions_json jsonb NOT NULL DEFAULT '[]'::jsonb,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  status text NOT NULL DEFAULT 'running',
  model_version text,
  notes text
);

CREATE INDEX IF NOT EXISTS simulation_runs_building_started_idx
  ON simulation_runs(building_id, started_at DESC);

-- LEGACY (EAV): kept so anything still referencing it keeps working, but the
-- write/read path of record is now the wide sim_zone_15m below (spine merge,
-- decision #3 in docs/spine/CONFLICT_RESOLUTION.md). New runs do NOT write here.
CREATE TABLE IF NOT EXISTS simulation_results (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  simulation_run_id uuid NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
  timestamp timestamptz NOT NULL,
  zone_id uuid REFERENCES zones(id) ON DELETE SET NULL,
  device_id uuid REFERENCES devices(id) ON DELETE SET NULL,
  metric_name text NOT NULL,
  metric_value numeric NOT NULL,
  metric_unit text
);

CREATE INDEX IF NOT EXISTS simulation_results_run_idx
  ON simulation_results(simulation_run_id, timestamp);

-- Wide per-run simulation trajectory (spine storage, decision #3). One row per
-- (run, zone, 15-min step) — same wide shape as telemetry_zone_15m, so reading
-- a trajectory is a column select, not an EAV pivot. uuid keying (decision #2).
CREATE TABLE IF NOT EXISTS sim_zone_15m (
  simulation_run_id uuid NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
  zone_id           uuid NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
  timestamp         timestamptz NOT NULL,
  occupancy_count   numeric NOT NULL DEFAULT 0,
  temperature_c     numeric,
  setpoint_c        numeric,
  hvac_power_kw     numeric NOT NULL DEFAULT 0,
  lighting_power_kw numeric NOT NULL DEFAULT 0,
  plug_power_kw     numeric NOT NULL DEFAULT 0,
  total_power_kw    numeric NOT NULL DEFAULT 0,
  comfort_violated  boolean NOT NULL DEFAULT false,
  PRIMARY KEY (simulation_run_id, zone_id, timestamp)
);

CREATE INDEX IF NOT EXISTS sim_zone_15m_run_ts_idx
  ON sim_zone_15m(simulation_run_id, timestamp);

CREATE TABLE IF NOT EXISTS scenario_kpi (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  scenario_id uuid REFERENCES scenarios(id) ON DELETE SET NULL,
  baseline_run_id uuid REFERENCES simulation_runs(id) ON DELETE SET NULL,
  optimized_run_id uuid REFERENCES simulation_runs(id) ON DELETE SET NULL,
  baseline_kwh numeric,
  optimized_kwh numeric,
  saving_kwh numeric,
  saving_percent numeric,
  cost_saving_vnd numeric,
  peak_reduction_kw numeric,
  comfort_violation_delta_min numeric,
  co2_avoided_kg numeric,
  computed_at timestamptz NOT NULL DEFAULT now(),
  details_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS forecast_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  zone_id uuid REFERENCES zones(id) ON DELETE SET NULL,
  model_name text NOT NULL,
  model_version text NOT NULL,
  horizon_minutes integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL DEFAULT 'running',
  summary_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS forecast_predictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  forecast_run_id uuid NOT NULL REFERENCES forecast_runs(id) ON DELETE CASCADE,
  timestamp timestamptz NOT NULL,
  zone_id uuid REFERENCES zones(id) ON DELETE SET NULL,
  target_name text NOT NULL,
  predicted_value numeric NOT NULL,
  lower_bound numeric,
  upper_bound numeric
);

CREATE INDEX IF NOT EXISTS forecast_predictions_run_idx
  ON forecast_predictions(forecast_run_id, timestamp);

-- Rule catalog for the anomaly engine (spine merge). The engine reads enabled
-- rules from here instead of hardcoding thresholds; alerts reference rules via
-- alerts.alert_type = anomaly_rules.id. Seed: db/seed/anomaly_rules.sql
CREATE TABLE IF NOT EXISTS anomaly_rules (
  id          text PRIMARY KEY,          -- 'hvac_on_empty', ...
  name        text NOT NULL,
  description text,
  rule_type   text NOT NULL,             -- threshold | schedule_deviation | stuck_sensor | fault
  params      jsonb NOT NULL DEFAULT '{}'::jsonb,
  severity    text NOT NULL DEFAULT 'warning',
  enabled     boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  zone_id uuid REFERENCES zones(id) ON DELETE SET NULL,
  device_id uuid REFERENCES devices(id) ON DELETE SET NULL,
  alert_type text NOT NULL,
  severity text NOT NULL,
  message text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz
);

CREATE INDEX IF NOT EXISTS alerts_building_created_idx
  ON alerts(building_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Agent runtime tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  entrypoint text NOT NULL,                  -- chatbot|button|approval_resume
  button_action text,
  user_query text,
  intent text,
  status text NOT NULL DEFAULT 'running',    -- running|completed|failed|awaiting_approval
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  final_answer text,
  dashboard_cards jsonb NOT NULL DEFAULT '[]'::jsonb,
  viewer_updates jsonb NOT NULL DEFAULT '[]'::jsonb,
  scenario_config jsonb NOT NULL DEFAULT '{}'::jsonb,
  state_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS agent_runs_building_started_idx
  ON agent_runs(building_id, started_at DESC);

CREATE TABLE IF NOT EXISTS agent_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
  step integer NOT NULL,
  node text NOT NULL,
  status text NOT NULL DEFAULT 'completed',  -- running|completed|warning|failed
  message text NOT NULL,
  duration_ms integer,
  output_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_logs_run_idx ON agent_logs(run_id, step);

CREATE TABLE IF NOT EXISTS audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_type text NOT NULL,
  actor_id text NOT NULL,
  action_type text NOT NULL,
  entity_type text NOT NULL,
  entity_id text NOT NULL,
  payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_logs_created_idx
  ON audit_logs(created_at DESC);

-- ---------------------------------------------------------------------------
-- Reports / artifacts
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS reports (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  agent_run_id uuid REFERENCES agent_runs(id) ON DELETE SET NULL,
  report_type text NOT NULL,
  title text NOT NULL,
  status text NOT NULL DEFAULT 'completed',
  markdown_path text,
  pdf_path text,
  summary_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS artifacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid REFERENCES buildings(id) ON DELETE CASCADE,
  artifact_type text NOT NULL,
  file_path text NOT NULL,
  mime_type text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Vector-ready document tables (P1)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_type text NOT NULL,
  source_name text NOT NULL,
  source_path text,
  title text NOT NULL,
  chunk_text text NOT NULL,
  chunk_index integer NOT NULL DEFAULT 0,
  building_id uuid REFERENCES buildings(id) ON DELETE SET NULL,
  zone_id uuid REFERENCES zones(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS documents_building_idx ON documents(building_id);
CREATE INDEX IF NOT EXISTS documents_zone_idx ON documents(zone_id);
CREATE INDEX IF NOT EXISTS documents_doc_type_idx ON documents(doc_type);

CREATE TABLE IF NOT EXISTS document_embeddings (
  document_id uuid PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  embedding vector(1536),
  embedding_model text NOT NULL,
  embedding_dim integer NOT NULL,
  metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- ---------------------------------------------------------------------------
-- AI chat (Groq-mặc-định, OpenAI-compatible) + RAG bằng turbovec
-- Vector KHÔNG lưu ở Postgres (dùng turbovec ngoài, file storage); bảng kb_chunks
-- giữ TEXT + metadata, id (bigint) làm khoá tới turbovec IdMapIndex.
-- ---------------------------------------------------------------------------

-- Cấu hình LLM provider: chọn provider + key (ĐÃ MÃ HOÁ) + model. is_active = đang dùng.
CREATE TABLE IF NOT EXISTS provider_configs (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider    text NOT NULL,                 -- groq | openai | openrouter | together | ollama | custom
  model       text,
  base_url    text,
  api_key_enc text NOT NULL,                  -- Fernet ciphertext (llm/keystore.py); KHÔNG bao giờ lưu trần
  is_active   boolean NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS provider_configs_active_idx ON provider_configs(is_active) WHERE is_active;

CREATE TABLE IF NOT EXISTS chat_sessions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid REFERENCES buildings(id) ON DELETE CASCADE,
  user_id     text,
  title       text,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_sessions_building_idx ON chat_sessions(building_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id  uuid NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  role        text NOT NULL,                  -- user | assistant | tool
  content     text NOT NULL DEFAULT '',
  tool_calls  jsonb NOT NULL DEFAULT '[]'::jsonb,  -- tool nào đã gọi (truy vết)
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_messages_session_idx ON chat_messages(session_id, created_at);

-- Knowledge-base chunks cho RAG (policy, định nghĩa, tóm tắt report, Q&A cũ).
-- Embedding sống trong turbovec (file), id ở đây = id trong turbovec IdMapIndex.
CREATE TABLE IF NOT EXISTS kb_chunks (
  id          bigserial PRIMARY KEY,
  doc_type    text NOT NULL,                  -- policy | definition | report | qa
  title       text NOT NULL,
  content     text NOT NULL,
  building_id uuid REFERENCES buildings(id) ON DELETE SET NULL,
  metadata    jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS kb_chunks_doc_type_idx ON kb_chunks(doc_type);
