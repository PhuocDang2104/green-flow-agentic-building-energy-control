# GreenFlow Current Architecture Guide

Tài liệu này mô tả cách repo GreenFlow hiện đang vận hành: data đi từ đâu, database giữ gì, LangGraph chạy thế nào, API đang chia nhóm ra sao, và khi muốn triển khai tiếp thì nên nối vào điểm nào.

Các file chính đã đối chiếu:

- Backend app: `backend/greenflow/api/main.py`
- Database schema: `db/schema.sql`
- DB helper: `backend/greenflow/db.py`
- Agent graph: `backend/greenflow/agent/graph.py`
- Agent state/service: `backend/greenflow/agent/state.py`, `backend/greenflow/agent/service.py`
- Chat runtime: `backend/greenflow/chat/service.py`, `backend/greenflow/chat/data_tools.py`
- Frontend API client: `web/src/lib/api.ts`
- Frontend state: `web/src/stores/appStore.ts`
- Viewer: `web/src/components/viewer/GreenFlowViewer.tsx`

## 1. Nguyên lý tổng thể

GreenFlow không phải là BMS thật. Nó là lớp digital twin + simulation + agent decision ở phía trên BMS.

Luồng chuẩn:

```text
Building model / IFC / IDF / weather / tariff / occupancy
-> canonical database + static 3D assets
-> replay/live telemetry state
-> dashboard + 3D viewer
-> simulation / forecast / anomaly / policy
-> LangGraph agent proposes action
-> policy gate + approval
-> audit log / report / UI update
```

Nguyên tắc quan trọng nhất:

1. Database là nguồn sự thật cho building, zones, devices, telemetry, actions, simulation, agent runs, chat sessions.
2. 3D geometry là static asset, không sửa runtime. Runtime chỉ đổi visibility, colorize, opacity, highlight.
3. `entity_key` là khóa ổn định nối database, 3D object map, frontend store, agent và API.
4. AI không được tự bịa số. Số liệu phải đi qua DB query, simulation hoặc tool đã định nghĩa.
5. Action không được execute trực tiếp. Phải đi qua control -> simulation -> policy -> execution/approval -> audit.
6. "Now" trong demo không phải giờ hệ thống thật, mà là replay clock từ telemetry lịch sử.

## 2. Data Spine Chuẩn

### 2.1 Static data

Static data là dữ liệu mô tả tòa nhà và mapping.

Nguồn hiện tại:

- `data/greenflow_archetype.idf`
- `db/seed/normalized_building.json`
- `web/public/assets/buildings/greenflow_archetype/viewer-manifest.json`
- `web/public/assets/buildings/greenflow_archetype/xkt/*.xkt`
- `web/public/assets/buildings/greenflow_archetype/metadata/*.json`
- `web/public/assets/buildings/greenflow_archetype/mapping/xeokit_object_map.json`
- `data/electrical_distribution/*.csv`
- `data/knowledge_graph_build/*.csv|jsonl|md`

Static data nên được coi là immutable trong runtime. Nếu muốn thay đổi geometry/layer/mapping thì chạy lại pipeline build asset hoặc seed lại DB, không sửa trực tiếp trong UI.

### 2.2 Dynamic data

Dynamic data là telemetry và state theo thời gian.

Nguồn chính trong DB:

- `telemetry_zone_15m`: power, energy, cost, occupancy, comfort, setpoint theo zone.
- `telemetry_device_15m`: trạng thái/power/runtime theo device.
- `occupancy_zone_15m`: occupancy count/confidence.
- `weather_15m`: weather theo timestamp.
- `alerts`: anomaly/fault đang mở hoặc đã resolve.

Frontend lấy state qua:

- Poll API: `/api/state/latest`, `/api/kpi/current`, `/api/timeseries/building`
- WebSocket: `/ws/building/{building_id}/state`

Trong frontend, `useStateWebSocket()` nhận frame `state_tick` rồi ghi vào Zustand store:

```text
ws state_tick -> appStore.setReplay(timestamp, zones, building)
-> dashboard cards / zone table / 3D heatmap đọc từ store
```

### 2.3 Mapping giữa DB và 3D

Luồng 3D hiện tại:

```text
viewer-manifest.json
-> GreenFlowViewer loads XKT layers
-> xeokit_object_map.json maps xeokit object id -> entity_key/layer/type
-> click object -> selectedEntityKey
-> /api/entities/{entity_key}
```

DB cũng có bảng tương ứng:

- `geometry_assets`: layer nào có asset URL/metadata URL.
- `mesh_entity_map`: mesh/object id map về entity.

Frontend hiện đang load static manifest từ:

```ts
MANIFEST_URL = /assets/buildings/greenflow_archetype/viewer-manifest.json
```

API `/api/3d/viewer-manifest` cũng tồn tại để client ngoài web đọc manifest DB-backed.

## 3. Database Hiện Tại

Schema chính nằm ở `db/schema.sql`.

### 3.1 Core reference tables

| Table | Vai trò |
|---|---|
| `buildings` | Building root, timezone, location, source dataset |
| `floors` | Tầng, elevation, raw IFC guid |
| `zones` | Thermal zone/space, `entity_key`, diện tích, volume, risk |
| `rooms` | Room con trong zone |
| `devices` | HVAC, lighting, meter-like device, controllable flag |
| `device_systems` | Mapping device vào system IFC/HVAC |
| `meters` | Meter theo building/floor/zone |
| `cameras` | Camera source, privacy mode |
| `tariff_rules` | Giá điện/cost rule |

Quy ước khóa:

- UUID DB là khóa quan hệ nội bộ.
- `entity_key` là khóa ổn định cho UI/agent/3D.
- `raw_ifc_guid` giữ trace về IFC gốc.

### 3.2 Graph và 3D mapping

| Table | Vai trò |
|---|---|
| `entity_relations` | Quan hệ zone-device-floor-system, dùng cho semantic graph |
| `geometry_assets` | Danh sách layer 3D asset |
| `mesh_entity_map` | Xeokit object id -> DB entity/entity_key/layer |

Khi build feature liên quan 3D, phải giữ cùng một `entity_key` giữa:

```text
zones/devices.entity_key
mesh_entity_map.entity_key
xeokit_object_map.json.entity_key
frontend selectedEntityKey
```

### 3.3 Time-series

| Table | Vai trò |
|---|---|
| `telemetry_zone_15m` | Bảng wide chính cho zone telemetry |
| `telemetry_device_15m` | Bảng wide chính cho device telemetry |
| `occupancy_zone_15m` | Occupancy riêng |
| `weather_15m` | Weather/replay weather |

Repo đang ưu tiên wide table thay vì EAV cho runtime. Ví dụ `telemetry_zone_15m` có các cột `hvac_power_kw`, `lighting_power_kw`, `total_power_kw`, `energy_kwh`, `temperature_c`, `comfort_risk`.

Lý do: dashboard và API đọc nhanh, không phải pivot metric_name/metric_value.

### 3.4 Simulation/action/forecast

| Table | Vai trò |
|---|---|
| `actions` | Candidate/proposed/pending/executed/rejected action |
| `action_targets` | Target zone/device của action |
| `approval_requests` | Human approval queue |
| `scenarios` | Scenario config |
| `simulation_runs` | Mỗi lần chạy baseline/what-if/agent |
| `sim_zone_15m` | Trajectory wide theo run-zone-15m |
| `scenario_kpi` | Baseline vs optimized KPI |
| `forecast_runs` | Metadata forecast run |
| `forecast_predictions` | Forecast values |

`simulation_results` vẫn tồn tại legacy EAV, nhưng comment trong schema nói write/read path chuẩn hiện là `sim_zone_15m`.

### 3.5 Agent runtime

| Table | Vai trò |
|---|---|
| `agent_runs` | Một run LangGraph, status, final answer, cards, viewer updates |
| `agent_logs` | Timeline từng node, UI hiển thị như CI pipeline |
| `audit_logs` | Audit chung cho action/approval/report |

Quan trọng: Agent graph không chỉ trả response. Nó persist `state_json`, `dashboard_cards`, `viewer_updates`, `agent_logs`. UI đọc run/log để render progress và kết quả.

### 3.6 Reports, artifacts, chat, RAG

| Table | Vai trò |
|---|---|
| `reports` | Metadata report, markdown/pdf path |
| `artifacts` | File/object artifact |
| `documents`, `document_embeddings` | Pgvector-ready doc tables |
| `provider_configs` | LLM provider config, API key encrypted |
| `chat_sessions` | Chat conversation |
| `chat_messages` | User/assistant/tool transcript |
| `kb_chunks` | Text chunk cho RAG; vector thực nằm ngoài Postgres trong turbovec |

Chat RAG hiện dùng hybrid retrieval:

```text
query
-> dense search in turbovec
-> lexical full-text in Postgres kb_chunks
-> RRF fusion
-> reranker
-> LLM + function tools
```

## 4. LangGraph Nguyên Lý Hiện Tại

File chính: `backend/greenflow/agent/graph.py`.

Graph wrapper cố định:

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

Điểm quan trọng: LangGraph không hardcode mọi agent node thành edge riêng. Nó dùng `orchestration_planner` sinh plan, rồi `plan_executor` chạy từng node theo thứ tự.

### 4.1 State contract

State nằm ở `backend/greenflow/agent/state.py`.

Các nhóm field chính:

- Request context: `run_id`, `building_id`, `entrypoint`, `user_query`, `button_action`.
- Intent/plan: `intent`, `orchestration_plan`, `current_plan_step`.
- Semantic context: `building_summary`, `floors`, `zones`, `zone_equipment_map`, `abnormal_findings`.
- Dynamic state: `latest_zone_state`, `latest_device_state`, `weather_state`.
- Prediction/control/simulation/policy: `forecast_result`, `candidate_actions`, `selected_actions`, `simulation_result`, `policy_decisions`.
- UI output: `dashboard_cards`, `viewer_updates`, `final_answer`, `related_entities`.
- Observability: `agent_logs`, `errors`, `stop_reason`, `degraded_nodes`.

Nếu thêm node mới, phải thêm field state nếu node cần đọc/ghi dữ liệu có cấu trúc mới.

### 4.2 Plan nodes

`PLAN_NODES` hiện có:

| Node | Vai trò |
|---|---|
| `building_semantic` | Load semantic graph, zone/device, abnormal findings |
| `prediction` | Forecast load/comfort/peak risk |
| `control` | Sinh candidate actions và rank |
| `simulation` | Simulate selected actions |
| `policy` | Check guardrails/policy |
| `execution` | Mock execute hoặc tạo approval request |
| `report` | Render report |
| `compare` | Lấy latest baseline vs optimized |

Mỗi node trả `dict` update vào state. `plan_executor` merge update đó vào `working` state.

### 4.3 Logging và recovery

Mỗi step gọi `_log_step()` để ghi `agent_logs`.

Executor có:

- `max_steps`
- `timeout_ms`
- retry theo node
- fallback theo node
- `stop_reason`
- `degraded_nodes`

Logging không được phép làm vỡ run: `_log_step` swallow exception để agent vẫn chạy.

### 4.4 Entry points

Có 3 entrypoint trong state:

- `button`: user bấm nút ở UI Agents/Simulation.
- `chatbot`: chat có thể hỏi data hoặc trigger action.
- `approval_resume`: approval flow.

Button flow:

```text
POST /api/agent/run-optimization
-> service.start_run()
-> background service.execute_run()
-> LangGraph invoke()
-> agent_runs + agent_logs
```

Chat trigger action:

```text
POST /api/chat
-> ChatRuntime
-> LLM tool trigger_agent_action
-> service.start_run()
-> background thread execute_run()
```

Chat không bypass policy. Nó chỉ khởi động cùng workflow như button.

### 4.5 LLM trong repo

Cần tách rõ hai loại:

1. Agent core: deterministic là chính. `agent_llm_polish=false` mặc định trong config, nghĩa là agent run không phụ thuộc LLM để tính số/action.
2. Chat assistant: dùng `ChatRuntime`, `ModelRouter`, provider config/Groq/OpenAI-compatible, RAG + tools. Nếu provider lỗi, chat degrade thay vì làm vỡ server.

Nguyên tắc: LLM chỉ điều phối/diễn giải. Data thật phải qua tool.

## 5. API Hiện Tại

Backend include router trong `backend/greenflow/api/main.py`, tất cả dưới prefix `/api`.

Frontend gọi qua `web/src/lib/api.ts` với:

```ts
const BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";
```

Trong dev, WebSocket dùng thẳng port `8000` nếu frontend chạy ở `3000`.

### 5.1 Building/entity/state

| Frontend method | Backend endpoint | Data source |
|---|---|---|
| `buildings()` | `GET /api/buildings` | `buildings` |
| `zones()` | `GET /api/zones` | `zones` + latest state |
| `devices(zoneId)` | `GET /api/devices` | `devices` |
| `entity(key)` | `GET /api/entities/{entity_ref}` | zones/devices/mesh map |
| `entityNeighbors(key)` | `GET /api/entities/{entity_ref}/neighbors` | `entity_relations` |
| `latestState()` | `GET /api/state/latest` | latest telemetry |
| `zoneHistory()` | `GET /api/timeseries` | `telemetry_zone_15m` |
| `buildingTimeseries()` | `GET /api/timeseries/building` | aggregate zone telemetry |
| `kpis()` | `GET /api/kpi/current` | timeseries tool |
| `healthScore()` | `GET /api/kpi/health-score` | timeseries tool |

### 5.2 3D viewer

| Endpoint | Vai trò |
|---|---|
| `GET /api/3d/assets` | DB-backed asset rows |
| `GET /api/3d/object-map` | DB-backed mesh map |
| `GET /api/3d/viewer-manifest` | Manifest từ `geometry_assets` |

Frontend viewer hiện dùng static public assets cho tốc độ/cache:

```text
/assets/buildings/greenflow_archetype/viewer-manifest.json
/assets/buildings/greenflow_archetype/xkt/*.xkt
/assets/buildings/greenflow_archetype/mapping/xeokit_object_map.json
```

### 5.3 Agent/action/approval

| Frontend method | Endpoint | Ghi/đọc |
|---|---|---|
| `runOptimization()` | `POST /api/agent/run-optimization` | insert `agent_runs`, background graph |
| `runPrediction()` | `POST /api/agent/predict` | insert `agent_runs` |
| `peakStrategy()` | `POST /api/agent/peak-strategy` | insert `agent_runs` |
| `compareBaseline()` | `POST /api/agent/compare-baseline-optimized` | insert `agent_runs` |
| `agentRuns()` | `GET /api/agent/runs` | read `agent_runs` |
| `agentRunLogs(id)` | `GET /api/agent/runs/{id}/logs` | read `agent_logs` |
| `actions(status)` | `GET /api/actions` | read `actions/action_targets` |
| `approvals(status)` | `GET /api/approvals` | read `approval_requests/actions` |
| `approve(id)` | `POST /api/approvals/{id}/approve` | update approval/action + audit |
| `rejectApproval(id)` | `POST /api/approvals/{id}/reject` | update approval/action + audit |
| `policyConfig()` | `GET /api/policy-config` | read policy yaml |

### 5.4 Chat

| Frontend method | Endpoint | Vai trò |
|---|---|---|
| `chatQuery()` | `POST /api/chat` | RAG + tools + persist chat |
| `chatSessions()` | `GET /api/chat/sessions` | list history |
| `chatSessionMessages()` | `GET /api/chat/sessions/{id}/messages` | load transcript |

Chat tools hiện có:

- `get_building_kpi`
- `get_zone_timeseries`
- `get_top_consumers`
- `get_alerts`
- `list_zones`
- `trigger_agent_action`

Không có tool nào cho phép LLM tự viết SQL tự do.

### 5.5 Simulation/climate/forecast

| Frontend method | Endpoint | Vai trò |
|---|---|---|
| `simulations()` | `GET /api/simulations` | list simulation runs |
| `latestComparison()` | `GET /api/simulations/compare/latest` | latest baseline vs optimized |
| `comparisonSeries(metric)` | `GET /api/simulations/compare/series` | aligned series |
| `simulateRecommended()` | `POST /api/simulation/simulate-recommended-actions` | starts peak strategy run |
| `validateBaseline()` | `GET /api/simulations/validate-baseline` | backtest baseline |
| `saveScenario()` | `POST /api/scenarios/save` | save climate scenario JSON |
| `runIdfSimulation()` | `POST /api/simulations/run-idf` | currently surrogate climate response |

Climate endpoint name says IDF, but current implementation is surrogate heuristic. It is shaped so real EnergyPlus can replace it later without changing frontend.

### 5.6 Electrical graph APIs

Electrical APIs are file-backed, not primary Postgres-backed.

| Endpoint | Source |
|---|---|
| `/api/electrical/overview` | `data/electrical_distribution/board_annual_summary.csv` |
| `/api/electrical/scene` | generated electrical scene |
| `/api/electrical/boards` | board CSV |
| `/api/electrical/boards/{id}/timeseries` | Parquet via DuckDB |
| `/api/electrical/zones/{zone_id}/electrical` | allocation/mapping CSV |
| `/api/graph/entities/{entity_id}/neighbors` | KG edge CSV |
| `/api/graph/rag/answer` | pgvector answer helper |

Nếu artifact chưa build, API trả 503 và yêu cầu chạy:

```bash
python scripts/build_electrical_kg.py --all
```

### 5.7 Replay/WebSocket

| Endpoint | Vai trò |
|---|---|
| `POST /api/replay/stream` | bật/tắt replay stream |
| `GET /api/replay/status` | trạng thái stream |
| `WS /ws/building/{building_id}/state` | realtime state tick |

Replay clock khiến dashboard có dữ liệu "live" dù telemetry là lịch sử.

## 6. Frontend Runtime

### 6.1 State store

`web/src/stores/appStore.ts` giữ:

- `buildingId`
- `replayTimestamp`
- `zoneStates`
- `buildingLive`
- `selectedEntityKey`
- `activeMetric`
- `layers`
- `techHeatmap`
- `viewerUpdates`
- `chatbotOpen`
- `activeAgentRunId`

Layer mặc định:

```ts
{
  architecture: true,
  spaces: true,
  fenestration: false,
  structural: false,
  hvac: false,
  electrical: false
}
```

### 6.2 Viewer nguyên lý

`GreenFlowViewer`:

1. Fetch manifest.
2. Fetch object map.
3. Load XKT layer bằng `XKTLoaderPlugin`.
4. Map model theo `asset.layer`.
5. Apply layer visibility từ store.
6. Apply heatmap/metric từ telemetry state.
7. Click/hover object -> resolve entity.

Layer MEP hiện đã được ưu tiên render:

- `electrical` renderOrder cao.
- `hvac` renderOrder cao nhất.
- Khi bật HVAC/Electrical, architecture/structural/windows/spaces chuyển x-ray để không che MEP.
- MEP không bị x-ray và giữ opacity 1.

### 6.3 Chatbot UI

Chat panel gọi:

```text
POST /api/chat
GET /api/chat/sessions
GET /api/chat/sessions/{id}/messages
```

Chat history lưu localStorage session id:

```text
greenflow_chat_session_id
```

## 7. Cách Triển Khai Tiếp Cho Đúng

### 7.1 Thêm một API mới

Checklist:

1. Tạo router hoặc thêm endpoint trong `backend/greenflow/api/routers/*.py`.
2. Dùng `db_conn()`, `fetch_one()`, `fetch_all()` nếu đọc DB.
3. Không cho frontend gửi raw SQL.
4. Include router trong `backend/greenflow/api/main.py` nếu là file mới.
5. Thêm method trong `web/src/lib/api.ts`.
6. Thêm type trong `web/src/lib/types.ts` nếu cần.
7. UI gọi qua `api.method()`, không hardcode `fetch`.
8. Test bằng `/docs` hoặc frontend build.

### 7.2 Thêm một bảng DB

Checklist:

1. Sửa `db/schema.sql`.
2. Chọn khóa chính UUID hoặc composite key cho timeseries.
3. Nếu liên quan building thì luôn có `building_id`.
4. Nếu liên quan zone/device thì dùng FK đến `zones/devices`.
5. Nếu cần UI/3D/agent refer ổn định thì thêm `entity_key`.
6. Thêm index theo query chính, thường là `(building_id, timestamp DESC)` hoặc `(building_id, entity_key)`.
7. Update seed script nếu cần.

### 7.3 Thêm một 3D layer

Checklist:

1. Export XKT/metadata cho layer mới.
2. Thêm entry vào `viewer-manifest.json`.
3. Thêm object mapping vào `xeokit_object_map.json`.
4. Nếu DB-backed: thêm `geometry_assets` và `mesh_entity_map`.
5. Thêm label/color ở `web/src/lib/constants.ts`.
6. Nếu layer cần priority, thêm render order trong `GreenFlowViewer.tsx`.
7. Nếu layer click được, đảm bảo `entity_key` resolve qua `/api/entities/{key}`.

### 7.4 Thêm một LangGraph node

Checklist:

1. Tạo file node trong `backend/greenflow/agent/nodes/`.
2. Node nhận `GreenFlowState`, trả `dict`.
3. Thêm state field vào `state.py` nếu cần.
4. Add vào `PLAN_NODES` trong `graph.py`.
5. Add label trong `NODE_LABELS`.
6. Add summary trong `_summarize()` để UI log dễ hiểu.
7. Update planner để node có thể xuất hiện trong `orchestration_plan`.
8. Nếu node có side effect, cẩn thận retry/fallback.
9. Persist output cần xem lại `_finish_run()` trong `service.py`.

### 7.5 Thêm một chat tool

Checklist:

1. Thêm function trong `backend/greenflow/chat/data_tools.py`.
2. Query phải tham số hóa và whitelist input.
3. Thêm schema vào `TOOL_SPECS`.
4. Thêm vào `_DISPATCH`.
5. Tool đọc data thì không side-effect.
6. Nếu side-effect, phải whitelist rất chặt và đi qua agent/policy.

### 7.6 Thêm một dashboard feature

Checklist:

1. Xác định data source: DB/API/file artifact/static.
2. Nếu là state realtime, thêm vào WebSocket hoặc poll endpoint.
3. Nếu là historical, dùng `/timeseries` hoặc endpoint riêng.
4. Nếu liên quan selected entity, dùng `selectedEntityKey`.
5. Nếu cần 3D update, trả `viewer_updates` từ agent hoặc set store trực tiếp.
6. Không tính KPI quan trọng chỉ ở frontend nếu backend cần audit.

## 8. Những Điểm Cần Nhớ / Caveats

1. Climate `run-idf` hiện là surrogate, chưa phải EnergyPlus thật.
2. Electrical APIs file-backed, phụ thuộc artifact trong `data/electrical_distribution`.
3. Chat RAG vector nằm trong turbovec file, không nằm trong Postgres.
4. Frontend viewer load static manifest public, không phải `/api/3d/viewer-manifest`.
5. Replay clock làm "now" chạy theo dữ liệu lịch sử, nên đừng so với giờ hệ thống.
6. Agent execution hiện mock BMS command. Approval approve chỉ đổi status/audit, không gửi lệnh thật.
7. `entity_key` là contract quan trọng nhất. Đổi nó là làm vỡ viewer, API entity, agent và chart selection.

## 9. Mental Model Ngắn Gọn

Nếu bạn cần debug:

```text
UI sai số liệu?
-> check web/src/lib/api.ts method
-> check backend router
-> check db query/tool
-> check replayclock anchor
-> check seed/telemetry table
```

```text
3D click/highlight sai?
-> check viewer-manifest layer
-> check xeokit_object_map.json
-> check mesh_entity_map/entity_key
-> check /api/entities/{entity_key}
-> check appStore selectedEntityKey
```

```text
Agent run sai?
-> check /api/agent/runs/{id}
-> check /api/agent/runs/{id}/logs
-> check planner output
-> check node update dict
-> check service._finish_run persisted fields
```

```text
Chat trả lời sai số?
-> check tools_used trong chat response
-> check data_tools function
-> check DB query source
-> nếu không có tools_used mà có số liệu, cần sửa prompt/tool policy
```

