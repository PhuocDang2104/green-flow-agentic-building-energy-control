-- GreenFlow MVP database schema
-- PostgreSQL 15+

CREATE EXTENSION IF NOT EXISTS pgcrypto;

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
  requested_at timestamptz NOT NULL DEFAULT now(),
  decision_mode text NOT NULL DEFAULT 'recommendation',
  action_type text NOT NULL,
  status text NOT NULL DEFAULT 'proposed',
  reason text,
  confidence numeric,
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

CREATE TABLE IF NOT EXISTS simulation_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  baseline_label text,
  scenario_id text,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  status text NOT NULL DEFAULT 'running',
  model_version text,
  notes text
);

CREATE INDEX IF NOT EXISTS simulation_runs_building_started_idx
  ON simulation_runs(building_id, started_at DESC);

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

CREATE TABLE IF NOT EXISTS forecast_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id uuid NOT NULL REFERENCES buildings(id) ON DELETE CASCADE,
  zone_id uuid REFERENCES zones(id) ON DELETE SET NULL,
  model_name text NOT NULL,
  model_version text NOT NULL,
  horizon_minutes integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS forecast_predictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  forecast_run_id uuid NOT NULL REFERENCES forecast_runs(id) ON DELETE CASCADE,
  timestamp timestamptz NOT NULL,
  target_name text NOT NULL,
  predicted_value numeric NOT NULL,
  lower_bound numeric,
  upper_bound numeric
);

CREATE INDEX IF NOT EXISTS forecast_predictions_run_idx
  ON forecast_predictions(forecast_run_id, timestamp);

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
-- Vector-ready document tables
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

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_embeddings (
  document_id uuid PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  embedding vector(1536),
  embedding_model text NOT NULL,
  embedding_dim integer NOT NULL,
  metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- ---------------------------------------------------------------------------
-- Minimal seed guidance
-- ---------------------------------------------------------------------------
--
-- 1. Insert one row into buildings.
-- 2. Load floors, zones, rooms, devices, device_systems from extracted BIM JSON.
-- 3. Load telemetry tables from generated synthetic data.
-- 4. Write action / simulation / forecast outputs as the app runs.
-- 5. Populate documents + document_embeddings for README, transcript, policies,
--    BIM notes, and simulation summaries.
--
