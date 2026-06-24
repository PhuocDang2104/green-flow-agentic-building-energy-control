# GreenFlow - Huong dan trien khai tiep: data, database, LangGraph va API

Ngay doc repo: 2026-06-22

Tai lieu nay la snapshot theo code hien tai trong repo. Muc tieu la giup ban nam duoc:

- Du lieu di tu dau den dau.
- Database dang luu cai gi, bang nao la nguon su that.
- LangGraph dang dieu phoi agent nhu the nao.
- API hien co dang expose nhung gi cho frontend va chatbot.
- Khi trien khai tiep thi nen them vao cho nao de khong pha kien truc.

## 1. Ban do tong quan

GreenFlow khong phai BMS va khong dieu khien thiet bi that trong MVP. No la lop ra quyet dinh ben tren:

```text
IFC/IDF + weather + schedule + telemetry
  -> normalized building JSON + 3D assets
  -> PostgreSQL canonical database
  -> replay clock + latest state / time-series
  -> LangGraph orchestration
  -> candidate action
  -> counterfactual simulation
  -> policy guardrail
  -> mock execution / approval queue / reject
  -> audit log + dashboard cards + viewer highlights + report
```

Triet ly quan trong:

1. So lieu vat ly phai den tu telemetry, simulation, surrogate hoac query DB. LLM khong duoc bia so.
2. Action khong sua truc tiep "ket qua"; action chi sua schedule/setpoint/lighting factor/HVAC availability, roi engine tinh hau qua.
3. Geometry cua toa nha la tinh; runtime chi doi state, mau, highlight, opacity, label.
4. Moi action dang ke phai qua simulation va policy truoc khi duoc ghi vao queue/action log.
5. "Now" cua app la replay clock tren telemetry, khong phai wall-clock hien tai.

## 2. Data: nguyen ly chuan

### 2.1. Cac lop du lieu

Repo co 5 lop du lieu chinh:

| Lop | Noi dung | File/bang chinh |
|---|---|---|
| Raw/source | IFC/IDF, EPW, parquet, CCTV/video, model files | `data/`, `storage/`, scripts loader |
| Normalized contract | JSON trung gian de seed DB va build sim | `db/seed/normalized_building.json` |
| Static 3D assets | XKT/GLB/metadata/object map cho xeokit | `web/public/assets/buildings/greenflow_archetype/` |
| Runtime DB | metadata, graph, telemetry, sim, action, agent, report, chat | `db/schema.sql` |
| Object/vector storage | PDF/video/image qua MinIO; turbovec index trong storage | `storage/processed/vector/kb.tvim`, MinIO |

### 2.2. Normalized JSON la hop dong trung gian

`db/seed/normalized_building.json` la hop dong giua BIM/IDF extractor va DB seed. No gom:

- `building`: thong tin toa nha.
- `floors`: tang.
- `zones`: live thermal zones co telemetry/action.
- `devices`: thiet bi ao/that duoc map vao zone.
- `entity_relations`: quan he semantic.
- `schedules`, `setpoints`: input cho simulation/action.
- `surfaces`, `fenestrations`: dung cho IDF archetype cu; voi IFC moi, geometry nam trong XKT.

Hai duong sinh normalized:

- `scripts/build_3d_assets_ifc.py`: duong chinh hien tai, doc enriched IFC, sinh 6 layer XKT va normalized JSON. Full building co nhieu space render duoc, nhung chi curate mot tap live zones de co telemetry/action.
- `scripts/build_3d_assets.py`: duong cu tu `data/greenflow_archetype.idf`, van giu cho test va fallback.

### 2.3. ID: tach UUID noi bo va entity_key ben ngoai

Database dung UUID lam primary key noi bo. Frontend, 3D viewer va agent dung `entity_key`/`mesh_id` de resolve doi tuong.

Quy uoc:

- `zones.id`, `devices.id`, `floors.id`: UUID noi bo, dung FK.
- `zones.entity_key`, `devices.entity_key`: id on dinh cho viewer/agent/API.
- `mesh_entity_map.mesh_id`: object id tu xeokit/XKT.
- `mesh_entity_map.entity_key`: noi mesh voi zone/device/semantic entity.
- `raw_ifc_guid`: giu GUID goc khi co.

Khi trien khai tiep, khong nen hardcode UUID. UI va agent nen di qua `entity_key`, API/backend resolve sang UUID khi query DB.

### 2.4. Replay clock: "hien tai" cua digital twin

Telemetry co the la du lieu nam 2025 hoac du lieu recorded/offline. Vi vay moi query latest/current phai dung:

```python
greenflow.replayclock.anchor()
```

Khong dung `now()` that cho telemetry, vi se bi rong hoac lech mua.

File lien quan:

- `backend/greenflow/replayclock.py`
- `backend/greenflow/agent/tools/db_tool.py`
- `backend/greenflow/agent/tools/timeseries_tool.py`
- `backend/greenflow/api/ws.py`

Bien moi truong:

- `REPLAY_NOW`: pin demo vao mot moc ISO neu muon.
- Rong thi anchor = `max(timestamp)` cua telemetry.
- `REPLAY_SPEED_SECONDS`: toc do ticker WebSocket.

### 2.5. Telemetry co ten `_15m` nhung co the chua 30 phut

Bang `telemetry_zone_15m` va `telemetry_device_15m` la bang time-series record. Ten bang giu theo quy uoc, nhung loader real data co ghi ro co truong hop du lieu 30 phut va khong upsample.

Khong nen viet logic gia dinh cung "moi ngay luon 96 point" tru khi dang xu ly seed synthetic/demo. Neu can tinh theo step, hay dua vao timestamp thuc te.

### 2.6. Geometry tinh, state dong

3D viewer load:

- `viewer-manifest.json`
- `xkt/<layer>.xkt`
- `metadata/<layer>_metadata.json`
- `mapping/xeokit_object_map.json`

Runtime state den tu:

- REST: `/api/state/latest`, `/api/entities/{entity}/state`, `/api/timeseries`
- WS: `/ws/building/{building_id}/state`
- Agent viewer updates: `agent_runs.viewer_updates`

Khong can rebuild XKT khi nhiet do, occupancy, power thay doi. Chi colorize/highlight entity trong frontend.

### 2.7. Telemetry vs simulation

Phai tach ro:

- `telemetry_zone_15m`: state recorded/measured/replayed cua toa nha.
- `simulation_runs`: metadata mot lan chay sim.
- `sim_zone_15m`: trajectory cua tung simulation run, dang wide.
- `scenario_kpi`: cache KPI baseline vs optimized moi nhat.

Bang `simulation_results` EAV cu van ton tai de tuong thich, nhung duong ghi/doc record hien tai la `sim_zone_15m`.

## 3. Data pipeline hien co

### 3.1. Demo seed pipeline

Lenh chinh:

```bash
python scripts/build_3d_assets_ifc.py
python scripts/seed_demo.py
```

`seed_demo.py` lam cac viec:

1. Xoa demo building UUID `b0000000-0000-0000-0000-000000000001`.
2. Seed `buildings`, `floors`, `zones`, `devices`.
3. Seed `entity_relations`.
4. Seed `geometry_assets` va `mesh_entity_map` tu object map.
5. Seed tariff, cameras.
6. Sinh telemetry zone/device/occupancy/weather.
7. Seed baseline + optimized simulation runs.
8. Seed scenarios.

### 3.2. Real data pipeline vao demo building

`scripts/load_real_into_demo.py` aggregate telemetry 188 zone that ve cac demo archetype zone. Muc dich: frontend/3D khong doi nhung so lieu hien thi co nguon EnergyPlus-derived.

Luu y quan trong: script nay duoc viet cho duong demo IDF archetype cu voi cac key `zone_storey0_open_office`, `zone_storey0_office`, `zone_storey0_meeting`, `zone_storey0_amenity`, `zone_storey0_circulation`. Duong seed IFC hien tai trong `build_3d_assets_ifc.py` curate khoang 14 live zones voi `entity_key` la IFC-derived `zone_<guid>`. Truoc khi dung script nay, hay check `SELECT entity_key FROM zones`; neu DB dang la IFC seed thi can viet mapper aggregate moi hoac dung loader 188-zone building rieng.

Dung khi:

- Ban muon giu UI demo hien tai.
- Ban co `zone_state_15m.parquet` va `archetype_zone_map.json`.
- Ban chap nhan aggregate nhieu zone that vao live zones demo.

### 3.3. Real data pipeline thanh building thu hai

`scripts/load_real_telemetry.py` nap 188 zone thanh building rieng. Dung khi:

- Ban muon tien toi UI/agent cho full 188 zone.
- Ban can giu raw IFC GUID va deterministic uuid5.
- Ban khong muon pha demo building.

### 3.4. Real data DuckDB path

`scripts/load_real_data.py` doc DuckDB final timeseries, map zone id ve repo zone keys, thay telemetry demo. Script nay co nhieu gia tri suy dien nhu occupancy/co2/comfort/cost.

Dung khi ban co DuckDB output dung format script yeu cau.

## 4. Database: nguyen ly va nhom bang

Schema chinh nam o `db/schema.sql`, dung PostgreSQL + `pgcrypto` + `vector`.

### 4.1. Core reference tables

| Bang | Vai tro |
|---|---|
| `buildings` | Toa nha, timezone, source dataset |
| `floors` | Tang theo building |
| `zones` | Thermal zones/live spaces, co `entity_key`, area, room_type |
| `rooms` | Room con cua zone, hien it duoc dung |
| `devices` | HVAC/electrical/plug/board/ahu..., co controllable/risk/status |
| `device_systems` | Mapping device vao system |
| `meters` | Meter metadata |
| `cameras` | CCTV/video source theo zone |
| `tariff_rules` | Bieu gia dien/cost |

Quy tac:

- `zones.entity_key` unique theo building.
- `devices.entity_key` unique theo building.
- Zone/device nen co `risk_level` de policy va UI dung.

### 4.2. Semantic graph va 3D mapping

| Bang | Vai tro |
|---|---|
| `entity_relations` | Graph semantic bang SQL, khong dung Neo4j trong P0 |
| `geometry_assets` | Danh sach layer XKT/metadata cua building |
| `mesh_entity_map` | Noi xeokit object id voi entity DB/entity_key |

Quan he hay gap:

- `Building HAS_FLOOR Floor`
- `Floor HAS_ZONE Zone`
- `Device LOCATED_IN Zone`
- `Device SUPPLIES_AIR_TO Zone`
- `AHU SERVES AirTerminal`

API lien quan:

- `/api/entities/{entity_ref}`
- `/api/entities/{entity_ref}/neighbors`
- `/api/3d/assets`
- `/api/3d/object-map`
- `/api/3d/viewer-manifest`

### 4.3. Time-series tables

| Bang | Vai tro |
|---|---|
| `telemetry_zone_15m` | Row state theo zone va timestamp |
| `telemetry_device_15m` | Row state theo device va timestamp |
| `occupancy_zone_15m` | Occupancy rieng, co source_type |
| `weather_15m` | Weather theo location/timestamp |

Primary key:

- `telemetry_zone_15m`: `(timestamp, zone_id)`
- `telemetry_device_15m`: `(timestamp, device_id)`
- `occupancy_zone_15m`: `(timestamp, zone_id)`
- `weather_15m`: `(timestamp, location_name)`

Cot quan trong trong `telemetry_zone_15m`:

- Occupancy: `occupancy_count`, `occupancy_state`, `occupancy_confidence`
- Comfort: `temperature_c`, `humidity_pct`, `co2_ppm`, `comfort_risk`
- Energy: `hvac_power_kw`, `lighting_power_kw`, `plug_power_kw`, `total_power_kw`, `energy_kwh`, `cost_vnd`
- Control context: `setpoint_c`, `peak_risk`, `anomaly_label`, `scenario_id`

### 4.4. Action, simulation, forecast, alert

| Bang | Vai tro |
|---|---|
| `actions` | Action do agent de xuat/ghi lai |
| `action_targets` | Target zone/device cua action |
| `approval_requests` | Human approval queue |
| `scenarios` | Cau hinh scenario/demo |
| `simulation_runs` | Metadata run baseline/agent/what-if |
| `sim_zone_15m` | Ket qua simulation wide theo run-zone-time |
| `scenario_kpi` | KPI comparison baseline vs optimized |
| `forecast_runs`, `forecast_predictions` | Cho forecast persisted |
| `anomaly_rules` | Catalog rule cho anomaly scan |
| `alerts` | Alert/FDD output |

Action status hien tai:

- `proposed`
- `pending_approval`
- `approved`
- `executed`
- `rejected`
- `blocked`

Simulation storage hien tai:

- Ghi run metadata vao `simulation_runs`.
- Ghi trajectory vao `sim_zone_15m`.
- Ghi comparison vao `scenario_kpi`.
- Doc chart qua `greenflow.sim.sim_store.read_run_series()`.

### 4.5. Agent runtime

| Bang | Vai tro |
|---|---|
| `agent_runs` | Moi lan chay LangGraph |
| `agent_logs` | Log tung node/step, UI poll de hien timeline |
| `audit_logs` | Audit chung cho agent/action/approval |

`agent_runs.state_json` la noi luu snapshot output quan trong cua run: intent, findings, forecast, actions, policy, simulation, report, related entities, errors.

### 4.6. Report/artifact

| Bang | Vai tro |
|---|---|
| `reports` | Metadata report, markdown path, pdf path |
| `artifacts` | File artifact generic |

PDF/report moi duoc serve qua:

- `/api/reports`
- `/api/reports/{report_id}`
- `/api/media/{key}` neu nam trong MinIO.
- `/storage/...` cho legacy local storage path.

### 4.7. Chat/RAG/provider

Chat da HOP NHAT ve MOT bo nao duy nhat (ChatRuntime):

1. `/api/chat`: bo nao chat chinh — short-term memory (chat_sessions/messages)
   + long-term RAG (kb_chunks) + function-calling tools (gom trigger_agent_action
   de khoi chay workflow run, tien do stream ra run-log UI).
2. `/api/agent/chat`: alias DEPRECATED, delegate sang dung ChatRuntime o tren.
   LangGraph graph chi con la workflow engine cho button + triggered run.

Bang lien quan `/api/chat`:

| Bang | Vai tro |
|---|---|
| `provider_configs` | Luu provider/model/base_url/key da ma hoa |
| `chat_sessions` | Session chat |
| `chat_messages` | Message history + tool calls |
| `kb_chunks` | Text chunk cho RAG, id la key sang turbovec |
| `documents`, `document_embeddings` | Pgvector-ready legacy/readiness |

Vector index khong nam trong Postgres trong path chat moi. No nam o file turbovec:

```text
storage/processed/vector/kb.tvim
```

Theo `config.py`, RAG chat mac dinh dung:

- Embedder: `bge-m3` (`BAAI/bge-m3`, 1024 dim), co fallback hashing neu model/lib khong load duoc.
- Reranker: `BAAI/bge-reranker-v2-m3`, co fallback giu thu tu neu thieu model.
- Hybrid retrieval: dense turbovec + lexical Postgres full-text, fuse bang RRF, roi rerank.

## 5. LangGraph: nguyen ly va flow hien tai

Implementation chinh:

- `backend/greenflow/agent/graph.py`
- `backend/greenflow/agent/state.py`
- `backend/greenflow/agent/service.py`
- `backend/greenflow/agent/nodes/*`

### 5.1. Graph co dinh, plan linh hoat

Graph that trong code:

```text
START
  -> input_router
  -> intent_classifier
  -> orchestration_planner
  -> plan_executor
  -> response_composer
  -> audit_logger
  -> END
```

No khong tao rat nhieu edge re nhanh trong LangGraph. Tinh "agentic" nam o `orchestration_plan`: planner quyet dinh `plan_executor` se goi node nao theo thu tu.

### 5.2. GreenFlowState la hop dong giua cac node

`GreenFlowState` la `TypedDict`, gom:

- Request context: `run_id`, `building_id`, `entrypoint`, `button_action`, `user_query`.
- Intent/plan: `intent`, `orchestration_plan`.
- Semantic: `building_summary`, `floors`, `zones`, `zone_equipment_map`, `abnormal_findings`.
- Dynamic state: latest zone/device/weather.
- Prediction: forecast, comfort risk, peak risk, demand forecast, confidence.
- Control: candidate/ranked/selected/final action plan.
- Simulation: simulation result, baseline-vs-optimized.
- Policy/approval: policy decisions, approval required, approval requests.
- Output: final answer, cards, viewer updates, report path.
- Observability: logs, errors.

Khi them node moi, hay them field state ro rang neu output se duoc node sau hoac UI dung.

### 5.3. Entrypoint

Co 3 entrypoint trong state:

| Entrypoint | Den tu dau | Cach chay |
|---|---|---|
| `button` | `/api/agent/run-optimization`, `/predict`, `/peak-strategy`, report buttons | Async background task, UI poll logs |
| `chatbot` | noi bo (khong con expose qua HTTP — chat di qua ChatRuntime `/api/chat`) | Graph van ho tro entrypoint nay |
| `approval_resume` | Da khai bao trong state/intent | Hien tai approval resolve truc tiep qua service, chua resume graph thuc su |

### 5.4. Planner hien tai

Button plans:

| Button | Plan |
|---|---|
| `run_optimization` | building_semantic -> prediction -> control -> simulation -> policy -> execution |
| `run_prediction` | building_semantic -> prediction |
| `peak_strategy` | building_semantic -> prediction -> control -> simulation -> policy -> execution |
| `compare_baseline_optimized` | building_semantic -> compare |
| `building_semantic_report` | building_semantic -> report |
| `hvac_elec_report` | building_semantic -> report |

Chat intents map sang cac plan tuong tu:

- `semantic_query`: building_semantic
- `energy_query`: building_semantic -> prediction
- `comfort_query`: building_semantic -> prediction
- `what_if_simulation_query`: building_semantic -> prediction -> control -> simulation
- `optimization_request`: full optimization
- `baseline_comparison_query`: building_semantic -> compare
- `report_request`: building_semantic -> report

### 5.5. Cac node/agent con

| Node | File | Viec lam |
|---|---|---|
| Building Semantic | `nodes/building_semantic.py` | Doc building/floor/zone/device/state/graph, tim abnormal findings, missing metadata |
| Prediction | `nodes/prediction.py` | Forecast ngan han schedule-aware; best-effort day-ahead demand neu ML co san |
| Control | `nodes/control.py` | Sinh candidate actions rule-based, rank bang quick estimate/surrogate |
| Simulation | `nodes/simulation.py` | Chay baseline vs action, persist sim runs/KPI |
| Policy | `nodes/policy_node.py`, `policy.py`, `policy.yaml` | Phan loai auto/approval/reject bang rule thuan |
| Execution | `nodes/execution.py` | Ghi actions, targets, approvals, audit; mock execution |
| Report | `nodes/report.py` | Tao markdown/PDF report tu state |
| Composer | `nodes/composer.py` | Tao final_answer, dashboard_cards, viewer_updates |
| Compare | `_compare` trong `graph.py` | Lay latest scenario_kpi |

Khong co Anomaly Agent rieng trong LangGraph. Bat thuong runtime trong flow agent do Building Semantic Agent suy ra tu graph + state + schedule. Ngoai ra co batch anomaly engine rieng o `agent/anomaly.py` ghi `alerts`.

### 5.6. Action lifecycle chuan

```text
abnormal_findings + forecast
  -> control candidate actions
  -> quick_estimate / surrogate scoring
  -> selected actions
  -> simulation baseline vs optimized
  -> policy evaluate
  -> final_action_plan
  -> execution node
  -> actions/action_targets/approval_requests/audit_logs
```

Policy decisions:

- `auto_run`: ghi action status `executed`.
- `approval_required`: ghi action status `pending_approval`, tao `approval_requests`.
- `rejected`: ghi action status `blocked`.

Approval API hien tai khong resume LangGraph. `service.resolve_approval()` cap nhat `approval_requests`, `actions`, va ghi `audit_logs`. Approved van la mock execution, khong gui BMS command.

### 5.7. LLM trong LangGraph

Trong `backend/greenflow/agent/llm.py`:

- Ho tro `openai` va `anthropic` neu key co san.
- Neu khong co provider/key, flow chay deterministic fallback.
- LLM chi dung de refine intent hoac viet lai text/explanation.
- Action selection, simulation, policy la deterministic.

Luu y: `config.py` hien dat `llm_provider` default la `groq` cho chat stack moi, nhung `agent/llm.py` chi doc `openai`/`anthropic`. Vi vay LangGraph agent van co the chay fallback neu khong cau hinh OpenAI/Anthropic.

## 6. Simulation va policy

### 6.1. Action catalog

File: `backend/greenflow/sim/actions.py`

Action type hien co:

- Low risk: `lighting_reduction`, `turn_off_non_critical_lighting`, `hvac_eco_mode`, `hvac_setback_light`, `alert_or_ticket`
- Medium risk: `pre_cooling`, `early_hvac_shutdown`, `ventilation_adjustment`, `peak_load_reduction`, `demand_response`
- High risk: `whole_building_hvac_shutdown`

Action chi chua schedule modifiers:

- `lighting_factor`
- `setpoint_delta_c`
- `hvac_off`
- `start_hour`, `end_hour`
- `target_zone_keys`

### 6.2. Simulation engines

File chinh:

- `backend/greenflow/agent/tools/simulation_tool.py`
- `backend/greenflow/sim/runner.py`
- `backend/greenflow/sim/synthetic_baseline.py`
- `backend/greenflow/sim/kpi.py`
- `backend/greenflow/sim/sim_store.py`

`simulate_actions()` uu tien:

1. Neu co telemetry ngay replay, baseline = measured day tu `telemetry_zone_15m`, optimized = counterfactual apply actions tren baseline.
2. Neu khong co telemetry, fallback synthetic engine.
3. `run_simulation()` co the dung EnergyPlus neu `ENERGYPLUS_BIN` va `WEATHER_EPW` ton tai, neu fail thi fallback synthetic.

KPI comparison:

- `saving_kwh`
- `saving_percent`
- `cost_saving_vnd`
- `peak_reduction_kw`
- `comfort_violation_delta_min`
- `co2_avoided_kg`
- `hvac_kwh_delta`
- `lighting_kwh_delta`

### 6.3. Policy guardrail

File:

- `backend/greenflow/agent/policy.yaml`
- `backend/greenflow/agent/policy.py`
- `backend/greenflow/agent/regret.py`

Auto-run chi duoc neu:

- Auto actions enabled.
- Action nam trong allowed list.
- Zone type khong bi block.
- Setpoint delta khong vuot nguong.
- Occupancy confidence va forecast confidence du nguong.
- Comfort risk sau action thap.
- Peak risk sau action thap.
- So zone anh huong khong qua gioi han.
- Khong vi pham regrettable substitution.

Medium-risk actions nhu `pre_cooling`, `peak_load_reduction`, `demand_response` mac dinh approval required.

`whole_building_hvac_shutdown` bi reject.

## 7. API hien tai

Base path backend: `/api`. WebSocket: `/ws`.

Frontend typed client nam o `web/src/lib/api.ts`.

### 7.1. Health va WebSocket

| Method | Path | Vai tro |
|---|---|---|
| GET | `/api/health` | Health check |
| WS | `/ws/building/{building_id}/state` | Replay state tick, gui `{type: state_tick, timestamp, building, zones}` |

### 7.2. Building/floor/zone/device

| Method | Path | Vai tro |
|---|---|---|
| GET | `/api/buildings` | List buildings |
| GET | `/api/buildings/{building_id}` | Detail building |
| GET | `/api/buildings/{building_id}/summary` | Summary counts/area |
| GET | `/api/buildings/{building_id}/kpis` | KPI cards |
| GET | `/api/floors?building_id=` | Floors |
| GET | `/api/zones?building_id=&floor_id=` | Zones + latest_state |
| GET | `/api/zones/{zone_ref}` | Zone by UUID/entity_key + latest_state |
| GET | `/api/zones/{zone_ref}/devices` | Devices in zone |
| GET | `/api/zones/{zone_ref}/state?hours=24` | Zone history |
| GET | `/api/devices?building_id=&zone_id=` | Devices |
| GET | `/api/scenarios?building_id=` | Scenarios |

### 7.3. Entity inspector va semantic graph

| Method | Path | Vai tro |
|---|---|---|
| GET | `/api/entities/{entity_ref}` | Inspect zone/device/mesh by entity_key |
| GET | `/api/entities/{entity_ref}/state?hours=24` | State history cua entity |
| GET | `/api/entities/{entity_ref}/neighbors` | Quan he graph truc tiep |

`entity_ref` thuong la `entity_key` hoac xeokit object id.

### 7.4. State/time-series/KPI

| Method | Path | Vai tro |
|---|---|---|
| GET | `/api/state/latest?building_id=` | Latest zones/devices/weather tai replay anchor |
| GET | `/api/timeseries?zone={zone_ref}&hours=24` | Zone time-series |
| GET | `/api/timeseries/building?hours=24` | Building aggregate load curve |
| GET | `/api/kpi/current?building_id=` | KPI hien tai |

### 7.5. 3D viewer

Router prefix: `/api/3d`.

| Method | Path | Vai tro |
|---|---|---|
| GET | `/api/3d/assets?building_id=` | DB-backed geometry assets |
| GET | `/api/3d/object-map?building_id=&layer=` | DB-backed mesh map |
| GET | `/api/3d/viewer-manifest?building_id=` | Manifest tu DB |

Luu y: frontend hien load static manifest tu `/assets/buildings/greenflow_archetype/viewer-manifest.json` cho viewer, nhung DB-backed API van huu ich cho non-web clients/agent.

### 7.6. LangGraph agent APIs

Router prefix: `/api/agent`.

| Method | Path | Sync/async | Vai tro |
|---|---|---|---|
| POST | `/api/agent/run-optimization` | Async | Full optimize |
| POST | `/api/agent/predict` | Async | Prediction only |
| POST | `/api/agent/peak-strategy` | Async | Peak strategy workflow |
| POST | `/api/agent/compare-baseline-optimized` | Async | Compare latest baseline/optimized |
| POST | `/api/agent/report/building-semantic` | Async | Generate building semantic report |
| POST | `/api/agent/report/hvac-elec` | Async | Generate HVAC/electrical report |
| POST | `/api/agent/scan-anomalies` | Sync | Batch scan anomalies over last 24h replay |
| POST | `/api/agent/chat` | Sync | DEPRECATED alias -> ChatRuntime (dung `/api/chat`) |
| GET | `/api/agent/runs?building_id=&limit=20` | Read | List agent runs |
| GET | `/api/agent/runs/{run_id}` | Read | Run detail |
| GET | `/api/agent/runs/{run_id}/logs` | Read | Timeline logs |

Button request body:

```json
{
  "building_id": "optional",
  "scenario_config": {}
}
```

Agent chat body:

```json
{
  "building_id": "optional",
  "message": "Toa nha co van de gi?",
  "session_id": "optional"
}
```

### 7.7. Actions, approvals, policy, audit

| Method | Path | Vai tro |
|---|---|---|
| GET | `/api/actions?building_id=&status=&limit=50` | Action queue/history |
| GET | `/api/actions/{action_id}` | Action detail |
| GET | `/api/approvals?building_id=&status=pending` | Approval queue |
| POST | `/api/approvals/{approval_id}/approve` | Approve pending action |
| POST | `/api/approvals/{approval_id}/reject` | Reject pending action |
| GET | `/api/audit-log?limit=100` | Audit log |
| GET | `/api/policy-config` | Load policy YAML |

Approve/reject body:

```json
{
  "decided_by": "demo_user",
  "note": ""
}
```

### 7.8. Simulations

| Method | Path | Vai tro |
|---|---|---|
| GET | `/api/simulations?building_id=&limit=20` | List simulation runs |
| GET | `/api/simulations/compare/latest?building_id=` | Latest scenario_kpi |
| GET | `/api/simulations/compare/series?building_id=&metric=total_power_kw` | Aligned baseline/optimized series |
| GET | `/api/simulations/validate-baseline?building_id=&is_weekend=` | Backtest synthetic baseline vs telemetry |
| GET | `/api/simulations/{run_id}` | Simulation run metadata |
| GET | `/api/simulations/{run_id}/series?metric=total_power_kw` | Building-level sim series |
| POST | `/api/simulation/simulate-recommended-actions` | Async peak strategy simulation workflow |

Allowed sim metrics nam trong `backend/greenflow/sim/sim_store.py`:

- `total_power_kw`
- `hvac_power_kw`
- `lighting_power_kw`
- `plug_power_kw`
- `temperature_c`
- `zone_temperature_c`
- `setpoint_c`
- `occupancy_count`

### 7.9. Forecast APIs

| Method | Path | Vai tro |
|---|---|---|
| GET | `/api/forecast/demand?building_id=&horizon_h=24&weather_shift=0` | Day-ahead HVAC demand + peak + pre-cool recommendation |
| GET | `/api/forecast/occupancy?building_id=&horizon_h=24&step_min=60` | Occupancy profile forecast |

Neu thieu optional ML dependencies/model, API tra 503 thay vi doan bua.

### 7.10. Reports va media

| Method | Path | Vai tro |
|---|---|---|
| GET | `/api/reports?building_id=&limit=20` | List reports |
| GET | `/api/reports/{report_id}` | Report metadata |
| GET | `/api/media/{key:path}` | Stream MinIO object qua API proxy |

### 7.11. Alerts/FDD

| Method | Path | Vai tro |
|---|---|---|
| GET | `/api/alerts?building_id=&status=open&limit=100` | List alerts |
| GET | `/api/alerts/summary?building_id=` | Count alerts by severity |
| POST | `/api/alerts/{alert_id}/acknowledge` | Resolve alert |

### 7.12. AI chat/RAG/provider APIs

Day la bo nao chat DUY NHAT; `/api/agent/chat` la alias deprecated tro ve day.

| Method | Path | Vai tro |
|---|---|---|
| POST | `/api/chat` | RAG + function-calling historical data chat |
| GET | `/api/chat/sessions?building_id=` | List chat sessions |
| GET | `/api/chat/sessions/{session_id}/messages` | Session messages |
| GET | `/api/llm/providers` | Configured providers + known providers |
| POST | `/api/llm/providers` | Add provider, encrypt key, set active |
| POST | `/api/llm/providers/{config_id}/activate` | Activate provider |
| POST | `/api/chat/kb/reindex` | Rebuild turbovec index from `kb_chunks` |

RAG chat tool whitelist:

- `get_building_kpi`
- `get_zone_timeseries`
- `get_top_consumers`
- `get_alerts`
- `list_zones`
- `trigger_agent_action`

LLM khong sinh SQL tu do. No chi chon tool va dien tham so.

## 8. Frontend contract

Frontend Next.js doc API qua:

- `web/src/lib/api.ts`
- `web/src/lib/types.ts`
- `web/src/stores/appStore.ts`
- `web/src/hooks/useAgentRun.ts`
- `web/src/hooks/useStateWebSocket.ts`

Quy tac frontend hien tai:

- `NEXT_PUBLIC_API_BASE` default `/api`.
- Dev Next port 3000 thi WS noi truc tiep `localhost:8000`.
- Building default: `b0000000-0000-0000-0000-000000000001`.
- Agent button run async: start run -> poll `/agent/runs/{id}` va `/agent/runs/{id}/logs` moi 1.2s.
- WS state tick update `zoneStates` va `buildingLive` trong zustand store.
- Viewer updates tu agent duoc luu va apply highlight theo `entity_id`.

## 9. Cach trien khai tiep khong pha kien truc

### 9.1. Them metric telemetry moi

Checklist:

1. Them cot vao `db/schema.sql` neu metric la first-class.
2. Sua seed/loader lien quan: `seed_demo.py`, `load_real_*`.
3. Sua reader trong `db_tool.py`/`timeseries_tool.py` hoac router.
4. Sua type frontend trong `web/src/lib/types.ts`.
5. Sua chart/UI neu can.
6. Neu metric cung can sim, them cot vao `sim_zone_15m` va `METRIC_TO_COLUMN`.

### 9.2. Them action moi

Checklist:

1. Them action type va risk vao `sim/actions.py`.
2. Dinh nghia schedule modifiers trong `make_action()`.
3. Sua `control.py` de sinh action khi dieu kien dung.
4. Sua `policy.yaml` de allowed/approval/rejected.
5. Neu action anh huong sim khac setpoint/lighting/hvac_off, sua `_apply_actions()` va synthetic/IDF path.
6. Them test policy/simulation/agent plan.

### 9.3. Them LangGraph node moi

Checklist:

1. Them field output vao `GreenFlowState` neu can.
2. Tao file trong `backend/greenflow/agent/nodes/`.
3. Import va dang ky vao `PLAN_NODES` trong `graph.py`.
4. Them summary trong `_summarize()` de UI log co nghia.
5. Them node vao `BUTTON_PLANS` hoac `INTENT_PLANS` trong `planner.py`.
6. Dam bao node failure khong lam mat audit/log neu co the.

### 9.4. Them API moi

Checklist:

1. Tao/sua router trong `backend/greenflow/api/routers/`.
2. Include router trong `api/main.py` neu la router moi.
3. Dung `default_building_id()` va `resolve_zone()` neu lien quan.
4. Dung `_clean()` khi tra UUID/Decimal/datetime.
5. Them client function vao `web/src/lib/api.ts`.
6. Them TS type vao `web/src/lib/types.ts`.

### 9.5. Them du lieu BIM/IFC moi

Checklist:

1. Neu chi can render, build XKT/metadata/object map.
2. Neu can live telemetry/action, phai co zone trong `normalized_building.json` va `zones` DB.
3. Dam bao `entity_key` cua live zone khop object map.
4. Seed `mesh_entity_map` va `entity_relations`.
5. Nap telemetry theo `zone_id` UUID tu DB, khong theo entity_key truc tiep.

## 10. Nhung diem de nham

1. Chat da HOP NHAT: `/api/chat` la bo nao duy nhat (memory + RAG + tools);
   `/api/agent/chat` chi con la alias deprecated delegate sang ChatRuntime.
2. `docs/spine/openapi.yaml` la contract spine cu, khong khop hoan toan API code hien tai.
3. `simulation_results` la legacy EAV, duong record hien tai la `sim_zone_15m`.
4. `telemetry_zone_15m` co the chua 30-min data, dung timestamp thuc.
5. `now()` that khong phai "now" cua digital twin; dung replay `anchor()`.
6. LLM provider cho RAG chat va LLM trong LangGraph agent khong cung adapter.
7. Approve/reject hien tai chi cap nhat DB/mock execution, chua gui BMS.
8. EnergyPlus path co fallback synthetic; dung ket qua phai nhin `engine`.
9. Object storage MinIO khong expose truc tiep; browser lay qua `/api/media/{key}`.
10. Neu doi embedder dim, phai reindex turbovec va co the xoa index cu.

## 11. File map nen doc khi sua

| Viec | File nen bat dau |
|---|---|
| Database schema | `db/schema.sql` |
| Config/env | `backend/greenflow/config.py`, `.env.example` |
| DB helper | `backend/greenflow/db.py` |
| API app | `backend/greenflow/api/main.py` |
| API routers | `backend/greenflow/api/routers/*.py` |
| LangGraph flow | `backend/greenflow/agent/graph.py`, `state.py`, `service.py` |
| Agent planning | `backend/greenflow/agent/nodes/intent.py`, `planner.py` |
| Semantic graph | `backend/greenflow/agent/nodes/building_semantic.py`, `tools/graph_tool.py` |
| Prediction/control | `nodes/prediction.py`, `nodes/control.py` |
| Simulation | `agent/tools/simulation_tool.py`, `sim/*.py` |
| Policy | `agent/policy.yaml`, `agent/policy.py`, `agent/regret.py` |
| Reports | `agent/nodes/report.py`, `agent/tools/report_tool.py` |
| Chat/RAG | `chat/service.py`, `chat/data_tools.py`, `vector/*.py`, `llm/*.py` |
| 3D assets | `scripts/build_3d_assets_ifc.py`, `bim/ifc_geometry.py`, `bim/ifc_extractor.py` |
| Demo seed | `scripts/seed_demo.py` |
| Real data load | `scripts/load_real_into_demo.py`, `load_real_telemetry.py`, `load_real_data.py` |
| Frontend API | `web/src/lib/api.ts`, `types.ts` |
| Frontend state | `web/src/stores/appStore.ts` |

## 12. Lenh chay nhanh

Install:

```bash
make install
```

DB:

```bash
docker compose up -d db
```

Build assets + seed:

```bash
python scripts/build_3d_assets_ifc.py
python scripts/seed_demo.py
```

Backend/frontend:

```bash
make api
make web
```

Open:

```text
API docs: http://localhost:8000/docs
Web UI:   http://localhost:3000
```

Tests:

```bash
make test
```

## 13. Ket luan ngan gon

Neu trien khai tiep, hay giu 4 truc:

1. Database la source of truth; viewer/agent dung `entity_key`, DB dung UUID.
2. Moi state "hien tai" phai theo replay clock.
3. Moi action phai qua simulation va policy, LLM khong duoc quyet dinh safety.
4. API va frontend dang bam `web/src/lib/api.ts`; them endpoint thi cap nhat client/type cung luc.
