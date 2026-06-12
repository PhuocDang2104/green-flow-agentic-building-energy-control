# GreenFlow Database Schema

Schema này được thiết kế cho 4 nhu cầu cùng lúc:

1. lưu BIM canonical data,
2. lưu telemetry và simulation,
3. cho AI chat truy vấn metrics theo ngữ cảnh tòa nhà,
4. hỗ trợ graph query và vector retrieval.

## 1. Design Principles

- `IFC raw` giữ nguyên, không sửa.
- `canonical extracted data` là lớp trung gian chuẩn để app và agent dùng.
- `time-series` phải partition theo `timestamp`.
- `metrics` và `simulation` phải query được bằng SQL thuần.
- `relationships` nhiều bước nên nằm trong graph layer.
- `docs / notes / policies / summaries` nên index bằng vector search.

## 2. Relational Core Schema

### `buildings`

- `id` UUID, PK
- `name` text
- `location_name` text
- `timezone` text
- `building_type` text
- `source_dataset` text
- `created_at` timestamptz

### `floors`

- `id` UUID, PK
- `building_id` UUID, FK → `buildings.id`
- `floor_index` int
- `name` text
- `elevation_m` numeric
- `raw_ifc_guid` text

### `zones`

- `id` UUID, PK
- `building_id` UUID, FK
- `floor_id` UUID, FK → `floors.id`
- `name` text
- `room_type` text
- `area_m2` numeric
- `volume_m3` numeric
- `comfort_profile` text
- `risk_level` text
- `raw_ifc_guid` text
- `source_space_name` text

### `rooms`

- `id` UUID, PK
- `zone_id` UUID, FK → `zones.id`
- `name` text
- `capacity` int
- `usage_type` text
- `raw_ifc_guid` text

### `devices`

- `id` UUID, PK
- `building_id` UUID, FK
- `floor_id` UUID, FK nullable
- `zone_id` UUID, FK nullable
- `device_type` text
- `device_subtype` text
- `name` text
- `tag` text
- `controllable` boolean
- `risk_level` text
- `status` text
- `nominal_capacity` numeric nullable
- `nominal_power_kw` numeric nullable
- `raw_ifc_guid` text
- `raw_storey_guid` text

### `device_systems`

- `id` UUID, PK
- `device_id` UUID, FK → `devices.id`
- `system_guid` text
- `system_name` text
- `system_type` text
- `raw_ifc_guid` text

### `meters`

- `id` UUID, PK
- `building_id` UUID, FK
- `floor_id` UUID, FK nullable
- `zone_id` UUID, FK nullable
- `meter_type` text
- `unit` text
- `name` text
- `raw_ifc_guid` text

### `cameras`

- `id` UUID, PK
- `building_id` UUID, FK
- `floor_id` UUID, FK nullable
- `zone_id` UUID, FK nullable
- `name` text
- `video_source` text
- `privacy_mode` text
- `raw_ifc_guid` text nullable

### `tariff_rules`

- `id` UUID, PK
- `building_id` UUID, FK
- `metric_type` text
- `unit_price` numeric
- `currency` text
- `peak_start` time nullable
- `peak_end` time nullable
- `weekday_mask` int nullable
- `effective_from` date
- `effective_to` date nullable

## 3. Time-Series Schema

### `telemetry_zone_15m`

Partition key:
- `timestamp`

Columns:
- `timestamp` timestamptz
- `building_id` UUID
- `floor_id` UUID
- `zone_id` UUID
- `occupancy_count` int
- `occupancy_state` text
- `occupancy_confidence` numeric
- `temperature_c` numeric
- `humidity_pct` numeric
- `co2_ppm` numeric nullable
- `hvac_power_kw` numeric
- `lighting_power_kw` numeric
- `plug_power_kw` numeric nullable
- `total_power_kw` numeric
- `energy_kwh` numeric
- `cost_vnd` numeric
- `setpoint_c` numeric nullable
- `comfort_risk` text
- `peak_risk` text
- `anomaly_label` text nullable
- `scenario_id` text nullable

Primary key suggestion:
- `(timestamp, zone_id)`

### `telemetry_device_15m`

Columns:
- `timestamp` timestamptz
- `building_id` UUID
- `floor_id` UUID
- `zone_id` UUID nullable
- `device_id` UUID
- `device_type` text
- `status` text
- `mode` text nullable
- `setpoint_c` numeric nullable
- `power_kw` numeric
- `energy_kwh` numeric
- `runtime_minutes` int
- `fault_state` text nullable
- `command_source` text nullable
- `scenario_id` text nullable

Primary key suggestion:
- `(timestamp, device_id)`

### `occupancy_zone_15m`

- `timestamp` timestamptz
- `building_id` UUID
- `floor_id` UUID
- `zone_id` UUID
- `person_count` int
- `occupied` boolean
- `confidence` numeric
- `source_type` text

### `weather_15m`

- `timestamp` timestamptz
- `location_name` text
- `outdoor_temp_c` numeric
- `humidity_pct` numeric
- `wind_speed_mps` numeric nullable
- `cloud_cover_pct` numeric nullable
- `precipitation_mm` numeric nullable
- `solar_w_m2` numeric nullable
- `forecast_horizon_min` int nullable

### `actions`

- `id` UUID, PK
- `building_id` UUID
- `requested_at` timestamptz
- `decision_mode` text
- `action_type` text
- `status` text
- `reason` text
- `confidence` numeric nullable
- `created_by` text
- `simulation_run_id` UUID nullable

### `action_targets`

- `id` UUID, PK
- `action_id` UUID, FK → `actions.id`
- `target_type` text
- `target_id` UUID
- `parameters_json` jsonb

### `simulation_runs`

- `id` UUID, PK
- `building_id` UUID
- `baseline_label` text
- `scenario_id` text
- `started_at` timestamptz
- `completed_at` timestamptz nullable
- `status` text
- `model_version` text nullable
- `notes` text nullable

### `simulation_results`

- `id` UUID, PK
- `simulation_run_id` UUID, FK
- `timestamp` timestamptz
- `zone_id` UUID nullable
- `device_id` UUID nullable
- `metric_name` text
- `metric_value` numeric
- `metric_unit` text

### `forecast_runs`

- `id` UUID, PK
- `building_id` UUID
- `zone_id` UUID nullable
- `model_name` text
- `model_version` text
- `horizon_minutes` int
- `created_at` timestamptz
- `status` text

### `forecast_predictions`

- `id` UUID, PK
- `forecast_run_id` UUID, FK
- `timestamp` timestamptz
- `target_name` text
- `predicted_value` numeric
- `lower_bound` numeric nullable
- `upper_bound` numeric nullable

### `alerts`

- `id` UUID, PK
- `building_id` UUID
- `zone_id` UUID nullable
- `device_id` UUID nullable
- `alert_type` text
- `severity` text
- `message` text
- `created_at` timestamptz
- `resolved_at` timestamptz nullable

### `audit_logs`

- `id` UUID, PK
- `actor_type` text
- `actor_id` text
- `action_type` text
- `entity_type` text
- `entity_id` text
- `payload_json` jsonb
- `created_at` timestamptz

## 4. Graph Schema

Graph layer nên phản ánh quan hệ tòa nhà:

### Nodes

- `Building`
- `Floor`
- `Zone`
- `Room`
- `Device`
- `HVACSystem`
- `Meter`
- `Camera`
- `Action`
- `SimulationRun`
- `WeatherSnapshot`

### Edges

- `(:Building)-[:HAS_FLOOR]->(:Floor)`
- `(:Floor)-[:HAS_ZONE]->(:Zone)`
- `(:Zone)-[:HAS_ROOM]->(:Room)`
- `(:Zone)-[:HAS_DEVICE]->(:Device)`
- `(:Device)-[:BELONGS_TO_SYSTEM]->(:HVACSystem)`
- `(:Meter)-[:MEASURES]->(:Zone | :Building)`
- `(:Camera)-[:OBSERVES]->(:Zone)`
- `(:Action)-[:TARGETS]->(:Device | :Zone)`
- `(:SimulationRun)-[:VALIDATES]->(:Action)`
- `(:WeatherSnapshot)-[:INFLUENCES]->(:HVACSystem)`

## 5. Vector Schema

Vector store nên lưu tài liệu ngữ nghĩa, không lưu telemetry thô.

### `documents`

- `id` UUID, PK
- `doc_type` text
- `source_name` text
- `source_path` text nullable
- `title` text
- `chunk_text` text
- `chunk_index` int
- `building_id` UUID nullable
- `zone_id` UUID nullable
- `created_at` timestamptz

### `document_embeddings`

- `document_id` UUID, FK
- `embedding` vector
- `embedding_model` text
- `embedding_dim` int
- `metadata_json` jsonb

Lưu loại tài liệu:

- BIM specs
- seminar transcript
- policy notes
- simulation summaries
- maintenance notes
- Q&A history
- model cards

## 6. Mapping From Extractor Outputs

Extractor hiện tại nên map như sau:

- `building.json` → `buildings`
- `floors.json` → `floors`
- `spaces.json` → `zones` + `rooms`
- `hvac_devices.json` → `devices` + `device_systems`
- `electrical_devices.json` → `devices`
- `structural_elements.json` → `documents` hoặc `structural registry`
- `zone_equipment_map.json` → `zone`-`device` relation
- `floor_device_map.json` → fallback `floor`-`device` relation
- `materials_summary.json` → `documents` + `kpi/material summary`
- `network_summary.json` → `documents`
- `geometry_summary.json` → `documents`

## 7. Indexing Rules

- `telemetry_zone_15m(timestamp, zone_id)` B-tree + partitioning
- `telemetry_device_15m(timestamp, device_id)` B-tree + partitioning
- `zones(building_id, floor_id, name)`
- `devices(building_id, zone_id, device_type, controllable)`
- `actions(building_id, requested_at, status)`
- vector index trên `document_embeddings.embedding`

## 8. Minimum Schema for MVP

Nếu muốn cắt tối đa, chỉ giữ:

- `buildings`
- `floors`
- `zones`
- `devices`
- `device_systems`
- `telemetry_zone_15m`
- `telemetry_device_15m`
- `weather_15m`
- `actions`
- `simulation_runs`
- `simulation_results`
- `forecast_runs`
- `forecast_predictions`
- `documents`
- `document_embeddings`
- `audit_logs`

Đây là mức đủ để:

- chat hiểu ngữ cảnh tòa nhà,
- query metrics,
- chạy simulation baseline vs candidate,
- log action và explanation,
- làm RAG trên transcript / policy / BIM notes.
