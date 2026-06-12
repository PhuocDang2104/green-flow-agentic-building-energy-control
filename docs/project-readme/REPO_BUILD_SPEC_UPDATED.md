# GreenFlow — REPO_BUILD_SPEC cập nhật chuẩn

> File này là spec kỹ thuật để dựng repo GreenFlow. Đọc xong dev phải biết: dựng module nào, theo thứ tự nào, dữ liệu chảy ra sao, frontend có những page/component nào, LangGraph orchestration chạy như nào, EnergyPlus nằm ở đâu, database lưu gì, và action AI được kiểm chứng ra sao.  
>
> Bản cập nhật này hợp nhất: `README.md`, `REPO_BUILD_SPEC.md` cũ, `AGENT_DESIGN.md`, `AGENT_POLICY_PROPOSAL.md`, `DATABASE_SCHEMA.sql`, `DATA_AND_MODEL_PLAN.md`, `DEMO_SCENARIOS.md`, file LangGraph mới, và file 3D View / IFC Mapping mới.

---

## 0. One-line Product Definition

**GreenFlow** là một web platform dạng **agentic digital twin + simulation-first operations layer** cho tòa nhà văn phòng. Hệ thống đọc BIM/IFC, dựng 3D digital twin theo zone, chạy EnergyPlus/baseline simulation, dự đoán energy/comfort/peak risk, rồi đề xuất hoặc thực hiện action low-risk có guardrails, kèm simulation comparison, approval queue và audit log.

GreenFlow **không thay thế BMS**. Nó là lớp quyết định phía trên BMS hoặc mock environment:

```text
BIM/IFC + Weather + Occupancy + Telemetry + Tariff
→ canonical DB + 3D digital twin
→ EnergyPlus baseline / physical simulation
→ Prediction + Policy + Control reasoning
→ candidate action
→ what-if simulation / validation
→ approval / auto-action / reject
→ audit log + dashboard + report
```

---

## 1. Nguyên tắc kiến trúc bất di bất dịch

### 1.1. EnergyPlus là “tòa nhà ảo”, không bịa số vật lý

EnergyPlus tự tính các biến vật lý chính:

```text
zone temperature
cooling/heating load
lights/equipment electricity
facility electricity
comfort violation
peak demand
```

Dev chỉ tạo input:

```text
weather EPW
building geometry
thermal zones
materials/constructions
occupancy schedule
lighting schedule/load
plug load schedule
HVAC schedule/control setpoint
candidate action schedule
```

Không viết rule tự sinh nhiệt độ/cooling load để thay EnergyPlus. Rule/surrogate chỉ dùng làm **quick estimate** sau khi đã có baseline/simulation data.

---

### 1.2. IFC đóng băng, trạng thái sống nằm trong DB

IFC chỉ là nguồn static:

```text
ARCH As-Built
HVAC BuildingPermit
ELE BuildingPermit
STRUCT BuildingPermit
Terrain/Site
```

Quy tắc:

```text
IFC → extract một lần → canonical DB + GLB assets
raw_ifc_guid giữ làm anchor
realtime/mock state không ghi ngược vào IFC
tòa nhà đổi thật → re-extract IFC, không patch file IFC
```

Digital twin sống = `DB state keyed by entity_id/raw_ifc_guid`.

---

### 1.3. Action AI phải được kiểm chứng bằng baseline vs agent run

Mỗi action quan trọng phải được so sánh theo counterfactual:

```text
baseline run:
  cùng weather + occupancy + schedule fixed

agent/optimized run:
  cùng weather + occupancy
  nhưng có action AI nhúng vào control schedule
```

KPI:

```text
saving_kwh
cost_saving
peak_reduction_kw
comfort_violation_delta
comfort_risk_before_after
policy_decision
action_trace
```

Không trình bày là “điều khiển EnergyPlus realtime từng phút”. MVP là **simulation-first what-if + mock action**.

---

### 1.4. Không có Anomaly Agent riêng

Mọi bất thường đi qua **Building Semantic Agent**.

Ví dụ:

```text
HVAC chạy khi zone empty
lighting load cao ngoài giờ
cooling load cao hơn baseline
comfort risk cao nhưng airflow thấp
device không map được vào zone
meter/floor mapping sai
occupancy confidence thấp
```

Building Semantic Agent đọc:

```text
semantic graph
current state
baseline/schedule
device-zone mapping
metadata quality
```

rồi trả `abnormal_findings`.

---

### 1.5. P0 stack phải gọn

P0 không dùng Neo4j, TimescaleDB, Redis Streams nếu chưa cần.

```text
PostgreSQL + pgvector
→ metadata
→ time-series partition
→ graph tables
→ vector docs/policies/reports

FastAPI
→ API + LangGraph runtime + simulation/ML integration

Next.js
→ 3-page dashboard + 3D viewer

EnergyPlus
→ batch simulation

LightGBM/XGBoost optional
→ surrogate/forecast P1
```

Neo4j/TimescaleDB/Redis chỉ là P2 nếu dữ liệu lớn hoặc query phức tạp.

---

## 2. Target MVP Scope

### 2.1. Building

Demo building:

```text
ARK_NordicLCA_Office_Concrete
ARCH As-Built Revit = source of truth
HVAC/ELE BuildingPermit = device layers + action targets
STRUCT = material/mass/LCA optional
Terrain = site/context/visualization optional
```

MVP không nhất thiết render toàn bộ 308 spaces chi tiết trong UI. Có thể chọn 6–20 demo zones trên 2–3 floors, nhưng DB/extractor nên hỗ trợ toàn bộ building.

---

### 2.2. Canonical resolution

```text
time resolution: 15 phút
space resolution: zone-level
control resolution: device-level hoặc zone-level
reporting resolution: floor/building-level
simulation mode: batch/counterfactual
realtime mode: mock/replay từ DB
```

---

### 2.3. Primary demo buttons

Chỉ giữ 5 button chính:

```text
1. Run Optimization
2. Generate Building Semantic Report
3. Generate HVAC/Elec Report
4. Simulate Peak-Hour Strategy
5. Compare Baseline vs Optimized
```

Không thêm button lẻ như “Detect Empty-Zone Waste” hoặc “Check Comfort Violation” trong P0. Các câu hỏi đó đi qua chatbot hoặc Building Semantic Agent.

---

## 3. Stack chính thức

| Layer | Chọn cho P0 | Ghi chú |
|---|---|---|
| Backend | FastAPI | Python thuận với ifcopenshell, EnergyPlus, ML |
| Agent runtime | LangGraph | Main Orchestrator + planner + tool nodes |
| DB | PostgreSQL 15+ | 1 DB chính |
| Vector | pgvector | P1/P2, dùng docs/policies/reports |
| Graph | `entity_relations` table + recursive CTE | Không Neo4j P0 |
| Time-series | Partitioned Postgres tables | Không TimescaleDB P0 |
| Simulation | EnergyPlus batch | Baseline/agent/counterfactual |
| ML | LightGBM/XGBoost/RandomForest | Forecast/surrogate P1 |
| Occupancy | YOLO pretrained + aggregation | Không nhận diện danh tính |
| Frontend | Next.js + React + TypeScript | 3 pages |
| 3D | Three.js / React Three Fiber + Drei | Load GLB/static assets |
| UI | Tailwind + shadcn/ui hoặc tương đương | Component-driven |
| Storage | local `/storage` P0, S3-compatible P2 | IFC, GLB, reports, E+ artifacts |
| Jobs | simple CLI/scripts P0 | Celery/RQ P2 nếu cần |

---

## 4. Repo structure chuẩn

```text
greenflow/
  README.md
  REPO_BUILD_SPEC.md
  docker-compose.yml
  .env.example
  pyproject.toml
  package.json                 # optional root scripts
  Makefile

  docs/
    PROJECT_PROPOSAL.md
    AGENT_DESIGN.md
    AGENT_POLICY_PROPOSAL.md
    BIM4LCA_DATA_SOURCES.md
    DATABASE_SCHEMA.md
    DATA_AND_MODEL_PLAN.md
    DEMO_SCENARIOS.md
    FRONTEND_UI_SPEC.md
    LANGGRAPH_SPEC.md

  db/
    schema.sql
    migrations/
      001_init.sql
      002_scenarios_runs_actions.sql
      003_geometry_assets.sql
      004_agent_state.sql
    seed/
      buildings_seed.sql
      demo_policy.yaml
      demo_scenarios.yaml
    fixtures/
      demo_zones.json
      demo_devices.json
      demo_zone_equipment_map.json

  storage/
    raw/
      ifc/
      videos/
      weather/
    processed/
      normalized/
      glb/
      energyplus/
      reports/
      models/

  bim/
    __init__.py
    extractor.py
    placement.py
    spatial_join.py
    ifc_to_normalized.py
    ifc_to_glb.py
    validation.py
    out/
      building.json
      floors.json
      rooms.json
      zones.json
      surfaces.json
      fenestrations.json
      hvac_equipment.json
      electrical_equipment.json
      structural_elements.json
      zone_equipment_map.json
      geometry_asset_map.json
      missing_metadata_report.json
    tests/
      test_placement_world_coords.py
      test_space_floor_mapping.py
      test_device_zone_mapping.py

  sim/
    __init__.py
    idf/
      baseline.idf
      templates/
    epjson/
    weather/
      hcmc.epw
    runner.py
    action_to_idf.py
    scenarios.py
    parser.py
    kpi.py
    tests/
      test_action_to_idf.py
      test_kpi_compare.py

  ml/
    __init__.py
    occupancy_yolo.py
    occupancy_aggregator.py
    train_forecast.py
    train_surrogate.py
    forecast_service.py
    features.py
    models/
    tests/

  agent/
    __init__.py
    state.py
    graph.py
    orchestrator.py
    planner.py
    routers.py
    nodes/
      input_router.py
      intent_classifier.py
      orchestration_planner.py
      plan_executor.py
      building_semantic.py
      prediction.py
      control.py
      simulation.py
      policy.py
      report.py
      pdf_tool.py
      response_composer.py
      audit_logger.py
      human_approval.py
      mock_execution.py
    tools/
      db_tool.py
      graph_tool.py
      timeseries_tool.py
      simulation_tool.py
      prediction_tool.py
      policy_tool.py
      viewer_tool.py
      report_tool.py
    prompts/
      intent_classifier.md
      orchestration_planner.md
      building_semantic_agent.md
      report_agent.md
      response_composer.md
    tests/
      test_policy.py
      test_orchestration_plans.py
      test_run_optimization_flow.py

  api/
    __init__.py
    main.py
    deps.py
    routers/
      buildings.py
      zones.py
      devices.py
      states.py
      scenarios.py
      simulations.py
      actions.py
      reports.py
      agent.py
      viewer.py
    schemas/
      building.py
      state.py
      action.py
      simulation.py
      report.py
      agent.py
    services/
      building_service.py
      state_service.py
      simulation_service.py
      action_service.py
      report_service.py
      viewer_service.py
    tests/

  web/
    package.json
    next.config.js
    tsconfig.json
    tailwind.config.ts
    public/
      models/
        office/
          arch_shell.glb
          spaces.glb
          thermal_zones.glb
          hvac.glb
          electrical.glb
          structural.glb
          terrain.glb
    src/
      app/
        layout.tsx
        page.tsx
        dashboard/
          page.tsx
        agent-actions/
          page.tsx
        simulation-baseline/
          page.tsx
      components/
        layout/
          AppShell.tsx
          TopBar.tsx
          SideNav.tsx
          TabBar.tsx
          PageHeader.tsx
        viewer/
          BuildingViewer.tsx
          GLBLayer.tsx
          LayerTogglePanel.tsx
          FloorSelector.tsx
          ZoneInspectorDrawer.tsx
          ViewerLegend.tsx
          EntityHighlighter.tsx
        dashboard/
          KpiCard.tsx
          WeatherCard.tsx
          OccupancyCard.tsx
          EnergyBreakdownChart.tsx
          ZoneStateTable.tsx
          DeviceStateTable.tsx
        agent/
          ChatbotPanel.tsx
          AgentLogTerminal.tsx
          ActionPlanCard.tsx
          ApprovalQueue.tsx
          PolicyDecisionBadge.tsx
          AuditLogTable.tsx
        simulation/
          ScenarioSelector.tsx
          BaselineOptimizedChart.tsx
          KpiDeltaCards.tsx
          SimulationRunTable.tsx
          ActionTraceTimeline.tsx
        shared/
          Button.tsx
          Card.tsx
          Badge.tsx
          StatusPill.tsx
          LoadingState.tsx
          EmptyState.tsx
      lib/
        api.ts
        types.ts
        constants.ts
        format.ts
      stores/
        viewerStore.ts
        appStateStore.ts
      hooks/
        useBuildingState.ts
        useAgentRun.ts
        useViewerHighlights.ts

  scripts/
    extract_bim.py
    convert_ifc_to_glb.py
    load_to_db.py
    generate_mock_telemetry.py
    run_baseline.py
    run_agent_variant.py
    train_models.py
    seed_demo.py
    export_report.py
```

---

## 5. Data source và IFC extraction

### 5.1. IFC source-of-truth

```text
ARCH As-Built
→ source chính cho floor, space, room, zone, envelope, material/construction, EnergyPlus geometry

HVAC BuildingPermit
→ source cho air terminals, ducts, pipes, valves, pumps, fans, coils, action targets

ELE BuildingPermit
→ source cho light fixtures, outlets, boards, cable trays, lighting/plug-load mapping

STRUCT BuildingPermit
→ material/mass/LCA optional, không blocker

Terrain
→ 3D context/shading optional, không dùng làm zoning chính
```

---

### 5.2. Extractor bắt buộc xử lý đúng placement

Các lỗi đã biết cần tránh:

```text
không dùng local placement làm world coordinate
không dùng IfcSpace.ObjectPlacement làm centroid phòng
không bỏ qua parent transform
không bỏ qua rotation IFC
không map device xuống basement do fallback nearest quá rộng
```

Implementation yêu cầu:

```text
bim/placement.py
→ recursive IfcLocalPlacement to 4x4 world matrix

bim/spatial_join.py
→ point-in-space footprint cho point devices
→ line/intersection mapping cho duct/pipe/cable tray
→ floor alias mapping HVAC/ELE ↔ ARCH

bim/validation.py
→ reject nếu contained_storey != mapped_floor mà không có lý do hợp lệ
```

---

### 5.3. Normalized JSON output

Extractor phải sinh:

```text
building.json
floors.json
rooms.json
zones.json
surfaces.json
fenestrations.json
materials.json
constructions.json
hvac_equipment.json
electrical_equipment.json
structural_elements.json
zone_equipment_map.json
energyplus_mapping.json
semantic_graph.json
geometry_asset_map.json
missing_metadata_report.json
mapping_quality_report.json
```

---

### 5.4. 3D asset output

Không render IFC trực tiếp trong web runtime. Convert trước:

```text
arch_shell.glb
spaces.glb
thermal_zones.glb
hvac.glb
electrical.glb
structural.glb
terrain.glb
```

Mỗi mesh phải có mapping:

```json
{
  "mesh_id": "mesh_000123",
  "ifc_global_id": "2H9sK...",
  "entity_id": "zone_level03_openoffice_east",
  "entity_type": "ThermalZone",
  "floor_id": "level_03",
  "layer": "thermal_zones",
  "asset_url": "/models/office/thermal_zones.glb"
}
```

---

## 6. Database schema P0

P0 dùng PostgreSQL + pgvector. Không thêm TimescaleDB/Neo4j.

### 6.1. Core canonical tables

Bắt buộc có:

```text
buildings
floors
zones
rooms
devices
device_systems
meters
cameras
tariff_rules
schedules
```

### 6.2. Graph tables

```sql
entity_relations (
  id uuid primary key,
  building_id uuid,
  src_entity_type text,
  src_entity_id uuid,
  relation_type text,
  dst_entity_type text,
  dst_entity_id uuid,
  confidence numeric,
  method text,
  properties jsonb
)
```

Dùng cho:

```text
Building HAS_FLOOR Floor
Floor HAS_ZONE Zone
Zone HAS_ROOM Room
Device LOCATED_IN Zone
AirTerminal SUPPLIES_AIR_TO Zone
LightFixture LOCATED_IN Zone
Duct PASSES_THROUGH Zone
Surface USES_CONSTRUCTION Construction
Action TARGETS Zone/Device
```

### 6.3. Geometry/3D mapping tables

```sql
geometry_assets (
  id uuid primary key,
  building_id uuid,
  layer text,
  asset_url text,
  asset_type text, -- glb, tiles, ifc
  created_at timestamptz
);

mesh_entity_map (
  id uuid primary key,
  asset_id uuid,
  mesh_id text,
  entity_type text,
  entity_id uuid,
  raw_ifc_guid text,
  floor_id uuid,
  layer text,
  properties jsonb
);
```

### 6.4. Time-series tables

Partition theo time nếu cần:

```text
zone_state_ts
device_state_ts
occupancy_ts
weather_ts
forecast_ts
simulation_output_ts
```

Common fields:

```text
id
building_id
entity_type
entity_id
timestamp
metric
value_num
value_text
unit
source
scenario_id
world_run_id
properties jsonb
```

### 6.5. Scenario, runs, actions

```text
scenarios
world_runs
decision_ticks
actions
action_targets
policy_decisions
approval_requests
audit_logs
scenario_kpi
comfort_profiles
```

### 6.6. Reports/artifacts

```text
artifacts
reports
document_chunks
embeddings
```

`document_chunks/embeddings` dùng pgvector P1/P2.

---

## 7. LangGraph architecture

### 7.1. Main graph

```text
START
  ↓
input_router
  ↓
intent_classifier
  ↓
orchestration_planner
  ↓
plan_executor
  ↓
response_composer
  ↓
audit_logger
  ↓
END
```

### 7.2. Entrypoint

```text
entrypoint = "button"
→ button_action map sang workflow template

entrypoint = "chatbot"
→ classify intent
→ entity resolver
→ Orchestration Planner tự lập plan

entrypoint = "approval_resume"
→ load checkpoint
→ apply human decision
→ execute/cancel
```

### 7.3. Shared GreenFlowState

```python
class GreenFlowState(TypedDict):
    request_id: str
    user_id: str
    building_id: str
    session_id: str
    entrypoint: str

    user_query: str | None
    button_action: str | None
    selected_floor_id: str | None
    selected_zone_ids: list[str]
    selected_device_ids: list[str]
    scenario_config: dict

    intent: str | None
    orchestration_plan: list[dict]
    current_plan_step: int

    building_summary: dict
    floors: list[dict]
    zones: list[dict]
    rooms: list[dict]
    zone_equipment_map: dict
    semantic_context: dict
    abnormal_findings: list[dict]
    missing_metadata: list[dict]

    latest_zone_state: dict
    latest_device_state: dict
    occupancy_state: dict
    weather_state: dict
    tariff_state: dict
    baseline_state: dict
    timeseries_context: dict

    forecast_horizon_minutes: int
    forecast_result: dict
    comfort_risk: dict
    peak_risk: dict
    forecast_confidence: float
    prediction_explanation: dict

    candidate_actions: list[dict]
    ranked_actions: list[dict]
    selected_action: dict | None
    final_action_plan: list[dict]

    simulation_request: dict
    simulation_result: dict
    baseline_vs_action: dict
    baseline_vs_optimized: dict

    policy_config: dict
    policy_decision: dict
    approval_required: bool
    approval_request: dict | None
    human_decision: dict | None

    execution_result: dict
    mock_environment_state: dict

    report_type: str | None
    report_markdown: str | None
    pdf_path: str | None
    dashboard_cards: list[dict]
    viewer_updates: list[dict]
    final_answer: str

    agent_logs: list[dict]
    audit_log: dict
    errors: list[dict]
```

---

## 8. Agent/tool design

### 8.1. Main Orchestrator

File:

```text
agent/orchestrator.py
agent/planner.py
agent/graph.py
```

Nhiệm vụ:

```text
validate input
classify intent
build orchestration plan
call nodes/tools
update state
handle errors/fallback
compose response
write audit log
```

---

### 8.2. Building Semantic Agent

File:

```text
agent/nodes/building_semantic.py
agent/tools/graph_tool.py
agent/tools/db_tool.py
```

Nhiệm vụ:

```text
load building/floor/zone hierarchy
load zone-equipment map
load graph neighborhood
load missing metadata
summarize abnormal findings using state + baseline + graph
provide context for Prediction/Control/Report
```

Không tạo `anomaly_agent.py`.

Output:

```json
{
  "semantic_context": {},
  "target_zones": [],
  "related_hvac_devices": [],
  "related_electrical_devices": [],
  "controllable_devices": [],
  "missing_metadata": [],
  "abnormal_findings": [],
  "confidence": 0.86
}
```

---

### 8.3. Prediction Agent

File:

```text
agent/nodes/prediction.py
agent/tools/prediction_tool.py
ml/forecast_service.py
```

Nhiệm vụ:

```text
forecast zone load
forecast zone temperature
forecast comfort risk
forecast building peak risk
return confidence + explanation
```

Không tự đề xuất action.

---

### 8.4. Control Agent

File:

```text
agent/nodes/control.py
```

Nhiệm vụ:

```text
identify opportunities
generate candidate actions
rank actions
select action/action plan for simulation
```

Candidate actions:

```text
lighting_reduction
turn_off_non_critical_lighting
hvac_eco_mode
hvac_setback_light
pre_cooling
early_hvac_shutdown
peak_load_reduction
demand_response
alert_or_ticket
```

---

### 8.5. Simulation Agent

File:

```text
agent/nodes/simulation.py
agent/tools/simulation_tool.py
sim/runner.py
sim/action_to_idf.py
```

MVP engines:

```text
rule_quick_estimate
surrogate_what_if
energyplus_batch
```

---

### 8.6. Policy Engine

File:

```text
agent/nodes/policy.py
agent/tools/policy_tool.py
agent/policy.py
```

Policy decision:

```text
auto_run
approval_required
rejected
```

Guardrail:

```text
blocked zone type
occupancy confidence
forecast confidence
comfort risk after
setpoint delta
action risk level
device criticality
regrettable_substitution_check
```

---

### 8.7. Report Agent + PDF Tool

File:

```text
agent/nodes/report.py
agent/nodes/pdf_tool.py
agent/tools/report_tool.py
```

Report types:

```text
building_semantic_report
hvac_elec_report
peak_strategy_report
baseline_vs_optimized_report
optimization_summary_report
```

PDF output saved to:

```text
storage/processed/reports/
```

---

## 9. Button workflows

### 9.1. Run Optimization

Goal: sinh action/action plan cuối cho toàn tòa nhà.

Plan template:

```text
Building Semantic Agent
→ Data Retrieval Tools
→ Prediction Agent
→ Control Agent
→ Simulation Agent
→ Policy Engine
→ policy_route
   ├─ auto_run → Mock Execution
   ├─ approval_required → Approval Queue
   └─ rejected → Reject Log
→ Compare Baseline vs Optimized
→ Response Composer
→ Audit Logger
```

UI output:

```text
expected saving
expected cost saving
peak reduction
comfort risk before/after
policy decision
approval queue
agent logs
viewer highlights
final action plan
```

---

### 9.2. Generate Building Semantic Report

Plan template:

```text
Building Semantic Agent
→ Data Retrieval optional
→ Report Agent
→ PDF Tool
→ Artifact Saver
→ Response Composer
```

Report sections:

```text
building overview
floor hierarchy
room/zone hierarchy
thermal zone structure
ARCH/HVAC/ELE/STRUCT mapping summary
zone-equipment mapping
material/envelope summary
missing metadata
abnormal state summary
EnergyPlus readiness
recommended next steps
```

---

### 9.3. Generate HVAC/Elec Report

Plan template:

```text
Building Semantic Agent
→ Data Retrieval Tools
→ Report Agent
→ PDF Tool
→ Response Composer
```

Report sections:

```text
HVAC equipment summary
air terminals / ducts / pipes / valves / fans / pumps
electrical lighting / outlets / boards / cable trays
zone-device mapping
controllable devices
device state if available
mapping confidence
unmapped devices
abnormal HVAC/ELE behavior
EnergyPlus usage
```

---

### 9.4. Simulate Peak-Hour Strategy

Plan template:

```text
Building Semantic Agent
→ Data Retrieval Tools
→ Prediction Agent
→ Control Agent generates peak strategies
→ Simulation Agent simulates alternatives
→ Policy Engine classifies risk
→ Response Composer
→ Audit Logger
```

Strategies:

```text
pre_cooling
lighting_reduction low-occupancy zones
hvac_eco_mode low-priority zones
peak_load_reduction
demand_response
delay_non_critical_load
```

Most peak strategies require approval in MVP.

---

### 9.5. Compare Baseline vs Optimized

Plan template:

```text
Load Baseline Result
→ Load Optimized Run / Action Audit Log
→ Compare Metrics
→ Report Agent optional
→ Response Composer
```

Metrics:

```text
energy consumption
cost
peak demand
HVAC load
lighting load
plug/equipment load
comfort violation
CO2 avoided estimate
action trace
policy decisions
approval status
```

---

## 10. Chatbot flow

Chatbot is not a separate autonomous agent. It is an interface to the Orchestrator.

```text
User Query
→ Intent Classifier
→ Entity Resolver
→ Orchestration Planner
→ Plan Executor
→ Response Composer
```

Intent list:

```text
semantic_query
hvac_elec_query
energy_query
comfort_query
occupancy_query
what_if_simulation_query
optimization_request
peak_strategy_query
baseline_comparison_query
report_request
explain_action_query
general_help
```

Example:

```text
“Tầng 3 có vấn đề gì không?”
→ Building Semantic Agent
→ Data Retrieval
→ abnormal findings summary
→ response + 3D highlights
```

Example:

```text
“Nếu tăng setpoint 1°C ở open office thì sao?”
→ Building Semantic Agent
→ Data Retrieval
→ Prediction Agent
→ Simulation Agent
→ Policy optional
→ response
```

---

## 11. Frontend UI/UX structure

GreenFlow web có 3 page chính:

```text
/dashboard
/agent-actions
/simulation-baseline
```

### 11.1. Global layout

Components:

```text
AppShell
TopBar
SideNav or TabBar
ChatbotPanel
NotificationCenter
GlobalBuildingSelector
FloorSelector
```

Top navigation:

```text
Dashboard
Agent & Actions
Simulation & Baseline
```

Persistent widgets:

```text
building selector
scenario selector
current timestamp / replay tick
weather summary
chatbot floating panel
```

---

### 11.2. Page 1 — Dashboard

Route:

```text
/dashboard
```

Purpose:

```text
3D digital twin + zone-level inspection
```

Main layout:

```text
Left/center: 3D Building Viewer
Right: Zone Inspector Drawer
Bottom/side: KPI cards + charts
```

Components:

```text
BuildingViewer
GLBLayer
LayerTogglePanel
FloorSelector
ViewerLegend
ZoneInspectorDrawer
KpiCard
WeatherCard
OccupancyCard
EnergyBreakdownChart
ZoneStateTable
DeviceStateTable
```

Layer toggles:

```text
Architecture
Spaces/Zones
HVAC
Electrical
Structural
Terrain
Energy
Comfort Risk
Occupancy
Action Targets
```

Dashboard state:

```text
selected_building_id
selected_floor_id
selected_zone_id
enabled_layers
view_mode
viewer_highlights
latest_zone_state
latest_device_state
```

---

### 11.3. Page 2 — Agent & Actions

Route:

```text
/agent-actions
```

Purpose:

```text
Run Optimization, xem agent logs, action plan, approval queue, audit log, chatbot.
```

Primary controls:

```text
Run Optimization button
Generate Building Semantic Report button
Generate HVAC/Elec Report button
ChatbotPanel
```

Components:

```text
AgentLogTerminal
ActionPlanCard
ApprovalQueue
PolicyDecisionBadge
AuditLogTable
PolicyConfigPanel
ChatbotPanel
ReportDownloadCard
```

Sections:

```text
Current Orchestrator Run
Agent Logs
Final Action Plan
Policy Decision
Human Approval Queue
Action History / Audit Log
Chatbot
```

---

### 11.4. Page 3 — Simulation & Baseline

Route:

```text
/simulation-baseline
```

Purpose:

```text
So sánh baseline fixed schedule với optimized/agent run.
Chạy Simulate Peak-Hour Strategy.
Hiển thị KPI counterfactual.
```

Primary controls:

```text
Simulate Peak-Hour Strategy button
Compare Baseline vs Optimized button
Scenario selector
Run selector
```

Components:

```text
ScenarioSelector
BaselineOptimizedChart
KpiDeltaCards
SimulationRunTable
ActionTraceTimeline
ComfortViolationChart
PeakDemandChart
ReportDownloadCard
```

KPI:

```text
baseline_kwh
optimized_kwh
saving_kwh
saving_percent
cost_saving
peak_reduction_kw
comfort_violation_delta
co2_avoided_estimate
```

---

## 12. API routes

### 12.1. Building/viewer

```text
GET /api/buildings
GET /api/buildings/{building_id}
GET /api/floors?building_id=
GET /api/zones?building_id=&floor_id=
GET /api/zones/{zone_id}
GET /api/devices?building_id=&zone_id=&floor_id=
GET /api/viewer/assets?building_id=
GET /api/viewer/mesh-map?asset_id=
POST /api/viewer/highlights
```

### 12.2. State/time-series

```text
GET /api/state/latest?building_id=
GET /api/state/zones?zone_ids=
GET /api/state/devices?device_ids=
GET /api/timeseries?entity_id=&metric=&start=&end=
GET /api/kpi/current?building_id=
```

### 12.3. Agent

```text
POST /api/agent/chat
POST /api/agent/run-optimization
GET /api/agent/runs/{run_id}
GET /api/agent/runs/{run_id}/logs
```

### 12.4. Actions/approval

```text
GET /api/actions?building_id=
GET /api/actions/{action_id}
GET /api/approvals?building_id=
POST /api/approvals/{approval_id}/approve
POST /api/approvals/{approval_id}/reject
POST /api/approvals/{approval_id}/modify
```

### 12.5. Reports

```text
POST /api/reports/building-semantic
POST /api/reports/hvac-elec
GET /api/reports/{report_id}
GET /api/artifacts/{artifact_id}/download
```

### 12.6. Simulation

```text
POST /api/simulations/run-baseline
POST /api/simulations/run-agent
POST /api/simulations/peak-strategy
GET /api/simulations/{run_id}
GET /api/simulations/compare?baseline_run_id=&optimized_run_id=
```

---

## 13. EnergyPlus implementation

### 13.1. MVP EnergyPlus objects

Required:

```text
Version
Timestep
Building
Site:Location
RunPeriod
SimulationControl
GlobalGeometryRules
Zone
BuildingSurface:Detailed
FenestrationSurface:Detailed
Material
Construction
People
Lights
ElectricEquipment
ZoneInfiltration:DesignFlowRate
DesignSpecification:OutdoorAir
ThermostatSetpoint:DualSetpoint
ZoneControl:Thermostat
ZoneHVAC:IdealLoadsAirSystem
Output:Variable
Output:Meter
Output:SQLite
```

### 13.2. IFC → EnergyPlus mapping

```text
IfcSpace → Zone/ThermalZone
IfcRelSpaceBoundary → surface adjacency
IfcWall/IfcSlab/IfcRoof → BuildingSurface:Detailed
IfcWindow/IfcDoor → FenestrationSurface:Detailed
IfcMaterial/IfcMaterialLayerSet → Material/Construction
IfcLightFixture → Lights by zone
IfcOutlet → ElectricEquipment by zone
IfcAirTerminal/CooledBeam → zone served metadata/action target
Duct/Pipe/CableTray → graph/3D only in MVP
```

### 13.3. Baseline and agent runs

```text
baseline:
  fixed schedule
  no AI action

agent:
  same weather
  same occupancy
  action schedule applied after decision tick
```

### 13.4. Output parser

Parse E+ SQLite/CSV to DB:

```text
Zone Mean Air Temperature
Zone Air Relative Humidity
Zone Ideal Loads Supply Air Total Cooling Energy
Zone Ideal Loads Supply Air Total Heating Energy
Zone Lights Electricity Energy
Zone Electric Equipment Electricity Energy
Electricity:Facility
Facility Total Electricity Demand Rate
```

---

## 14. Policy

### 14.1. Low-risk auto-action candidates

```text
lighting_reduction when zone empty N minutes
turn_off_non_critical_lighting outside work hours
hvac_eco_mode light
hvac_setback_light
alert_or_ticket
reminder action
```

### 14.2. Medium-risk approval required

```text
pre_cooling
dynamic_setpoint_many_zones
early_hvac_shutdown
ventilation_adjustment
floor_level_eco_mode
peak_load_curtailment
```

### 14.3. High-risk simulation/recommendation only

```text
whole_building_hvac_shutdown
critical/server/utility room override
strong ventilation reduction
aggressive demand-response curtailment
action when occupancy confidence low
action when forecast uncertainty high
```

### 14.4. Policy config

```yaml
auto_actions:
  enabled: true
  max_setpoint_delta_c: 1.5
  min_occupancy_confidence: 0.8
  empty_zone_delay_minutes: 15
  max_comfort_risk_after: 0.25
  max_peak_risk_after: 0.4
  forecast_horizon_minutes: 60
  allowed_zone_types:
    - open_office
    - meeting_room
    - hallway
  blocked_zone_types:
    - server_room
    - electrical_room
    - security_room
    - utility_room
  allowed_actions:
    - lighting_reduction
    - hvac_eco_mode
    - anomaly_alert

approval_required:
  - pre_cooling
  - floor_level_setback
  - ventilation_adjustment
  - early_shutdown
  - demand_response
```

---

## 15. Build order

| Phase | Priority | Task | Output |
|---|---:|---|---|
| 0 | P0 | Docker + Postgres + schema.sql | DB chạy |
| 1 | P0 | Load seed demo building/zones/devices | Metadata query được |
| 2 | P0 | BIM extractor minimal + normalized JSON | floors/zones/devices/map |
| 3 | P0 | Convert/prepare GLB assets | 3D viewer load được |
| 4 | P0 | FastAPI read APIs | frontend có data |
| 5 | P0 | Next.js shell + 3 pages + tabbar | UI route đầy đủ |
| 6 | P0 | Dashboard 3D viewer + layer toggles | Page 1 usable |
| 7 | P0 | EnergyPlus baseline run + parser | baseline trajectory trong DB |
| 8 | P0 | Agent state + Orchestrator + policy | action recommendation |
| 9 | P0 | Run Optimization workflow | full flow có logs |
| 10 | P0 | Simulation compare baseline vs agent | Page 3 KPI |
| 11 | P0 | Report Agent + PDF export | report download |
| 12 | P1 | YOLO occupancy demo | occupancy state |
| 13 | P1 | Forecast/surrogate model | prediction nhanh |
| 14 | P1 | Human approval resume/checkpoint | HITL hoàn chỉnh |
| 15 | P2 | pgvector docs/RAG | chatbot hỏi docs |
| 16 | P2 | Neo4j/Timescale/Redis if needed | scale-up |

Critical path demo:

```text
3D Dashboard thuyết phục
+ baseline vs optimized comparison sạch
+ Run Optimization có agent logs
+ policy chặn unsafe action
+ report PDF download
```

---

## 16. Environment variables

`.env.example`:

```env
APP_ENV=development
DATABASE_URL=postgresql+psycopg://greenflow:greenflow@localhost:5432/greenflow
OPENAI_API_KEY=
MODEL_NAME=gpt-4.1-mini
STORAGE_DIR=./storage
ENERGYPLUS_BIN=/usr/local/EnergyPlus-24-1-0/energyplus
WEATHER_EPW=./storage/raw/weather/hcmc.epw
DEFAULT_BUILDING_ID=
ENABLE_AUTO_ACTIONS=false
MAX_SETPOINT_DELTA_C=1.5
MIN_OCCUPANCY_CONFIDENCE=0.8
```

---

## 17. Test requirements

### 17.1. BIM tests

```text
test recursive placement world coordinates
test room/space floor mapping
test MEP device not all mapped to basement
test device-zone spatial join confidence
test geometry_asset_map has entity_id/mesh_id
```

### 17.2. Simulation tests

```text
baseline run produces output
action_to_idf modifies schedules only
same weather/occupancy for baseline and agent
kpi comparison deterministic
```

### 17.3. Policy tests

```text
low-risk lighting reduction allowed when zone empty
server_room action rejected
low occupancy confidence blocks auto-action
comfort risk after threshold blocks auto-action
pre-cooling requires approval
```

### 17.4. Agent tests

```text
button run_optimization creates expected plan
chatbot what-if query creates simulation plan
Building Semantic Agent returns abnormal_findings without Anomaly Agent
Response Composer returns dashboard_cards/viewer_updates
```

### 17.5. Frontend tests

```text
3 pages route correctly
tabbar navigation works
viewer loads GLB layer
layer toggles hide/show objects
agent log terminal renders run steps
approval card shows approve/reject/modify
baseline chart renders comparison data
```

---

## 18. Definition of Done

MVP repo được coi là đạt nếu:

```text
1. `docker compose up` chạy DB.
2. `make seed-demo` tạo building, zones, devices, scenarios.
3. `make run-api` chạy FastAPI.
4. `make run-web` mở được 3 pages.
5. Dashboard load được GLB + layer toggles.
6. Run Optimization tạo agent logs + final action plan.
7. Policy có thể auto/approval/reject.
8. Baseline vs optimized compare có KPI.
9. Building Semantic Report và HVAC/Elec Report export được PDF.
10. Audit log lưu được mọi action/report/simulation quan trọng.
```

---

## 19. Open decisions

Cần chốt khi implement:

```text
1. Số zone demo chính thức: 6–12 hay full 308 spaces.
2. Dùng schematic GLB trước hay full IFC-derived GLB.
3. EPW HCMC nguồn nào.
4. EnergyPlus geometry lấy trực tiếp từ ARCH As-Built hay dùng archetype simplified.
5. Lighting power: lấy từ ELE fixture count hay default theo room type.
6. HVAC phase 1: IdealLoadsAirSystem confirm.
7. Setpoint delta max: 1.0 / 1.5 / 2.0°C.
8. Peak tariff giả lập theo khung giờ nào.
9. Có cần login/auth cho pitch không.
10. Deploy target: local demo / Vercel + backend VM / Docker single host.
```

---

## 20. Final implementation note

Dev không được bắt đầu từ UI mock rời rạc. Thứ tự đúng là:

```text
canonical DB
→ seed demo data
→ 3D asset map
→ API
→ frontend 3 pages
→ EnergyPlus baseline
→ LangGraph orchestrator
→ policy/action/audit
→ reports
```

GreenFlow phải luôn giữ câu chuyện:

```text
understand building
→ inspect state
→ predict future
→ simulate action
→ apply policy
→ approve/auto/reject
→ compare baseline
→ explain and audit
```
