# GreenFlow Context README

Tài liệu này lưu lại ngữ cảnh làm việc hiện tại của GreenFlow. Mục tiêu là để bất kỳ lần mở repo sau nào cũng có thể đọc nhanh và hiểu:

- GreenFlow là gì.
- Dữ liệu đi vào từ đâu.
- EnergyPlus (`E+`) nằm ở đâu trong pipeline.
- AI làm gì, tạo `new state` như thế nào.
- Validate và simulation được tổ chức ra sao.
- Database, streaming, graph query, vector search nên thiết kế thế nào.

## 1. Product Summary

GreenFlow là nền tảng web cho facility manager vận hành tòa nhà văn phòng lớn theo hướng data-driven và simulation-first. Hệ thống kết hợp BIM4LCA, edge devices, CCTV occupancy, weather API, utility tariff và lịch vận hành để:

- hiển thị dashboard 3D theo zone,
- dự đoán trạng thái tương lai,
- đề xuất hoặc tự động thực hiện action low-risk,
- mô phỏng tác động trước khi áp dụng action thật,
- lưu audit trail để quản lý có thể kiểm soát.

GreenFlow không thay thế BMS. Nó là lớp quyết định phía trên hệ thống tòa nhà hiện có.

## 2. MVP Scope

### Target building

- Office building lớn.
- Khoảng 5-10 tầng.
- Nhiều loại phòng: open office, meeting room, lobby, hallway, pantry, utility/server room.
- State theo zone, device và floor.

### Realtime mode

- Realtime trong MVP là mock/replay từ data có sẵn.
- Mục tiêu là demo ổn định, không phụ thuộc hoàn toàn vào hạ tầng realtime thật.

### CCTV

- Dùng video public để demo YOLO person detection.
- Không làm nhận diện danh tính.
- Chỉ aggregate thành occupancy count/state/confidence theo zone.

### Data

- Dữ liệu thật khi có.
- Dữ liệu thiếu thì giả lập theo rule.
- Weather dùng API thật.
- Utility cost do team cấu hình.

## 3. Core Product Flow

Luồng chính của GreenFlow là:

```text
Data
→ E+ simulation / physical model
→ AI decision / policy / control reasoning
→ New state
→ Validate + Simulation
→ Approve / Auto-act / Audit
```

### Diễn giải

- `Data`: thu thập trạng thái hiện tại của tòa nhà.
- `E+`: mô hình vật lý EnergyPlus dùng để mô phỏng phản ứng của tòa nhà trước action candidate.
- `AI`: đọc state hiện tại, prediction, policy và simulation output để chọn action tốt nhất.
- `New state`: trạng thái dự đoán sau action.
- `Validate and Simulation`: so baseline với candidate action để kiểm tra energy, cost, comfort, peak risk.

## 4. Data Resolution

### Canonical resolution

Chuẩn chung cho toàn pipeline nên là:

- `time`: 15 phút
- `space`: zone-level
- `control`: device-level cho action, zone-level cho state
- `reporting`: floor/building-level tổng hợp

### Raw resolution by source

| Nguồn | Raw resolution | Canonical |
|------|----------------|-----------|
| CCTV / YOLO | frame-level hoặc 1-5 FPS demo | 15 phút occupancy state |
| Edge devices | 1 phút hoặc 5 phút | 15 phút |
| Weather API | hourly hoặc 15 phút | 15 phút |
| EnergyPlus | 1-5 phút simulation timestep | 15 phút output |
| BIM4LCA | static | building/zone/device graph |

## 5. BIM4LCA As Data Foundation

Ba zip BIM4LCA là nguồn building context chính.

### ARCH.zip

- Layout phòng.
- Mặt bằng.
- Space / room / zone.
- Diện tích.
- Vật liệu kiến trúc.
- Cửa, tường, sàn, mái, facade, shading.
- Geometry tổng thể cho digital twin hoặc schematic 3D model.

### STRUCTURAL.zip

- Cột, dầm, sàn, tường chịu lực, móng.
- Vật liệu kết cấu.
- Khối lượng cấu kiện.
- Mở rộng story về LCA / carbon / material reporting.

### HVAC.zip

- HVAC, MEP, electrical, sprinkler.
- Duct / pipe / equipment relation.
- Zone-equipment mapping.
- Edge device inventory cho mock telemetry.
- Đây là zip quan trọng nhất cho HVAC optimization.

### BIM extractor

Script extractor cho bộ `Office_Concrete_BuildingPermit` nằm tại:

- [bim_extractor.py](../tools/bim_extractor.py)

Script này xuất ra:

- `floors.json`
- `spaces.json`
- `zones.json`
- `hvac_devices.json`
- `electrical_devices.json`
- `structural_elements.json`
- `zone_equipment_map.json`
- `floor_device_map.json`
- `materials_summary.json`
- `network_summary.json`
- `geometry_summary.json`

Mục tiêu là tạo một lớp BIM trung gian đủ gọn để sinh synthetic telemetry và nối sang graph / simulation / ML.

## 6. Recommended Data Model

### Core entities

- `building`
- `floor`
- `zone`
- `room`
- `device`
- `meter`
- `camera`
- `tariff`
- `weather_snapshot`
- `telemetry`
- `occupancy`
- `action`
- `simulation_run`
- `forecast`
- `audit_log`

### Zone state fields

- `timestamp`
- `zone_id`
- `occupancy_count`
- `occupancy_state`
- `occupancy_confidence`
- `temperature_c`
- `humidity_pct`
- `hvac_power_kw`
- `lighting_power_kw`
- `total_power_kw`
- `comfort_risk`
- `cost_vnd_per_hour`

### Device state fields

- `device_id`
- `zone_id`
- `device_type`
- `status`
- `setpoint_c`
- `power_kw`
- `controllable`
- `last_action_id`

## 7. Architecture Decisions

### 7.1 EnergyPlus role

EnergyPlus là simulation engine vật lý. Nó không phải database, và cũng không thay cho AI.

Nó dùng để:

- đọc sensor / meter / internal variables,
- nhận actuator value,
- mô phỏng phản ứng của tòa nhà sau khi action được áp dụng,
- trả về trajectory mới để validate.

API phù hợp là EnergyPlus Data Transfer API / Python API, vì nó hỗ trợ đọc sensor và set actuator trong lúc simulation đang chạy.

### 7.2 Database architecture

Nên dùng polyglot storage nhưng giữ gọn:

- PostgreSQL: system of record cho metadata, action log, policy, KPI summary, simulation runs.
- Time-series table trong PostgreSQL hoặc TimescaleDB: telemetry, occupancy, weather, E+ output.
- Neo4j: semantic graph của building, zone, device, camera, action, dependency.
- pgvector: vector search cho RAG, policies, BIM specs, simulation summaries, Q&A.
- Object storage: video, BIM files, simulation artifacts, model files.

### 7.3 Streaming

Streaming dùng cho event transport, không phải nơi lưu lịch sử dài hạn.

Khuyến nghị:

- Redis Streams để làm ordered event bus.
- Consumer groups cho ingestor, feature builder, agent orchestrator, simulation runner, dashboard updater.
- Raw events retention ngắn hạn.
- Aggregated state phải được ghi vào DB chính.

### 7.4 Graph query

Graph query dùng khi cần hỏi quan hệ nhiều bước, ví dụ:

- zone nào phục vụ bởi thiết bị nào,
- camera nào map vào zone nào,
- action nào ảnh hưởng tới node nào,
- weather ảnh hưởng qua HVAC tới zone nào.

Không dùng graph cho aggregate KPI hoặc time-series analytics.

### 7.5 Vector database

Vector DB dùng cho text/semantic retrieval, không dùng cho telemetry thô.

Nên embed:

- BIM specs,
- policy,
- action explanation,
- simulation summaries,
- maintenance notes,
- Q&A history.

MVP có thể dùng `pgvector` ngay trong PostgreSQL để giảm độ phức tạp hệ thống.

## 8. Minimal System Flow

```text
BIM4LCA + CCTV + Edge + Weather + Tariff
→ streaming layer
→ operational DB + graph DB + vector DB
→ E+ simulation engine
→ AI / policy engine
→ new state
→ simulation validation
→ dashboard / approval / audit
```

## 9. Product Tabs

### Tab 1: Dashboard

- 3D building theo tầng và zone.
- Occupancy bằng chấm xanh hoặc density indicator.
- Device state và realtime metrics.
- Weather và anomaly context.

### Tab 2: Agent Actions

- Action history.
- Policy configuration.
- Approval queue.
- Chat / command với Orchestrator.
- Audit log.

### Tab 3: Simulation

- Baseline vs optimized.
- What-if scenarios.
- Energy / cost / comfort / peak KPI.
- Forecast validation.

## 10. Suggested Model Targets

MVP nên ưu tiên:

- energy forecast,
- temperature forecast,
- cost forecast,
- comfort risk,
- peak demand risk,
- occupancy aggregation,
- anomaly score.

Khởi đầu bằng model đơn giản, explainable:

- LightGBM,
- XGBoost,
- RandomForest,
- rule-based anomaly detection.

Sau đó mới mở rộng sang LSTM/TFT nếu dữ liệu đủ.

## 11. Agent Policy

Policy hiện tại ở trạng thái proposal, chưa phải triển khai final.

### Low-risk auto-action candidates

- lighting reduction khi zone empty,
- HVAC eco mode nhẹ,
- HVAC setback nhẹ,
- anomaly alert / reminder.

### Medium-risk

- pre-cooling,
- dynamic setpoint nhiều zone,
- early shutdown,
- ventilation reduction.

### High-risk

- whole-building shutdown,
- override critical room,
- aggressive curtailment.

### Guardrails

- giới hạn delta setpoint,
- occupancy confidence threshold,
- zone/device allowlist và denylist,
- audit log bắt buộc,
- rollback hoặc approval nếu confidence thấp.

## 12. Current Open Decisions

- Số tầng/zone chính thức sẽ thay đổi sau.
- BIM4LCA extract chính xác từ IFC hay native file cần kiểm tra thêm.
- Target model predict có thể thay đổi khi có data thật hơn.
- Policy auto-action cần user duyệt trước khi code.
- 3D model sẽ là schematic hay chi tiết còn phụ thuộc thời gian.

## 13. Supporting Docs

- [Project proposal](PROJECT_PROPOSAL.md)
- [BIM4LCA data sources](BIM4LCA_DATA_SOURCES.md)
- [Data and model plan](DATA_AND_MODEL_PLAN.md)
- [Agent design](AGENT_DESIGN.md)
- [Agent policy proposal](AGENT_POLICY_PROPOSAL.md)
- [Seminar transcript 2026-06-10](SEMINAR_TRANSCRIPT_2026_06_10.md)
- [Seminar improvement notes](SEMINAR_IMPROVEMENT_NOTES.md)
- [Database architecture diagram](DATABASE_ARCHITECTURE.md)
- [Database schema](DATABASE_SCHEMA.md)
- [Database schema SQL](DATABASE_SCHEMA.sql)
- [Local Docker Compose](../docker-compose.yml)
- [Environment example](../.env.example)
- [MVP delivery plan](MVP_DELIVERY_PLAN.md)
- [Demo scenarios](DEMO_SCENARIOS.md)
