# MVP Delivery Plan

Mục tiêu cuối cùng là một MVP deploy được để pitch, có ML model thật, có dashboard web, có simulation validation và có report/slide đầy đủ.

## MVP Definition

MVP phải demo được:

```text
Data input/replay
-> 3D dashboard
-> YOLO occupancy demo
-> weather API integration
-> model prediction
-> agent action/recommendation
-> policy approval/auto-action
-> simulation and KPI report
-> deployed web app
```

## Phase 0: Scope Alignment

Deliverables:

- Chốt building plan tạm thời: 5-10 tầng, số zone có thể thay đổi sau.
- Chốt model targets P0.
- Duyệt hoặc sửa `AGENT_POLICY_PROPOSAL.md`.
- Chọn demo video public cho YOLO.
- Chọn deployment target.

Output:

- Final MVP scope note.
- Data schema draft.
- Policy v1 approved.

## Phase 1: Data Foundation

Deliverables:

- Building config cho floor/zone/room/device/camera.
- Mock realtime telemetry generator/replayer.
- Weather API integration.
- Utility tariff config.
- YOLO video occupancy script hoặc pipeline demo.

Output:

- Unified zone state dataset.
- Device state dataset.
- Occupancy aggregation output.
- Weather-aligned timeline.

## Phase 2: ML Models

Deliverables:

- Baseline energy forecast model.
- Temperature forecast model.
- Cost forecast calculation/model.
- Comfort risk rule/model.
- Anomaly rules or simple anomaly model.

Output:

- Trained model artifacts.
- Evaluation metrics.
- Prediction API or exported prediction JSON.
- Model explanation note for report.

## Phase 3: Agent and Policy Engine

Deliverables:

- Orchestrator action generator.
- Policy checker for auto/approval/reject.
- Action queue.
- Audit log schema.
- Chat/command patterns.

Output:

- Agent recommendations with expected saving, risk, confidence and explanation.
- Auto-action only for approved low-risk policy.
- Approval queue for medium/high-risk action.

## Phase 4: Simulation

Deliverables:

- Baseline fixed schedule scenario.
- Agent optimized scenario.
- Heatwave/peak price scenario.
- High occupancy scenario.
- Equipment anomaly scenario.

Output:

- Energy/cost/comfort/peak comparison.
- Expected vs simulated/actual report.
- Frontend-ready simulation artifacts.

## Phase 5: Frontend MVP

Deliverables:

- Tab 1 dashboard with 3D building and zone state.
- Tab 2 agent action workspace.
- Tab 3 simulation validation.
- Responsive pitch-ready UI.
- Demo scenario selector.

Output:

- Deployable web app.
- Pitch flow for judges.

## Phase 6: Report and Slides

Deliverables:

- Technical report.
- Architecture diagram.
- Data/model explanation.
- Demo script.
- Pitch slides.

Output:

- Full package for hackathon pitch.

## Proposed Timeline

| Step | Priority | Notes |
|------|----------|-------|
| Scope/policy/model target alignment | P0 | Làm trước khi code nhiều |
| Data schema + mock replay | P0 | Nền cho frontend/model/agent |
| Forecast baseline | P0 | Model thật đầu tiên |
| 3D dashboard | P0 | Quan trọng cho pitch |
| Agent action queue | P0 | Thể hiện agentic workflow |
| Simulation comparison | P0 | Chứng minh hiệu quả |
| YOLO public video demo | P1 | Cần show occupancy thật |
| Advanced model/TFT | P2 | Chỉ làm nếu đủ data/thời gian |

## Risks

| Risk | Mitigation |
|------|------------|
| Data thật không đủ | Dùng mock/replay có schema rõ |
| YOLO video không giống CCTV thật | Framing là demo public video, output là occupancy aggregate |
| ML model chưa tốt | Bắt đầu baseline explainable, đo metrics rõ |
| Simulation bị xem là giả | Tách baseline/action, ghi rõ assumptions, dùng KPI nhất quán |
| Agent bị xem là thiếu an toàn | Human-in-the-loop và policy guardrail rõ ràng |

## Deployment Notes

Deployment target sẽ chốt sau. MVP có thể deploy theo hướng:

- Frontend Next.js trên Vercel hoặc equivalent.
- Backend/API trên cloud VM/container nếu cần realtime/API.
- Nếu thời gian gấp, có thể deploy frontend với static artifacts và demo API mock.

Ưu tiên deploy ổn định cho pitch hơn là tích hợp quá nhiều service dễ lỗi.
