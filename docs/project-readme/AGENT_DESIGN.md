# GreenFlow Agent Design

Tài liệu này lưu lại thiết kế agent cho GreenFlow MVP. Hướng triển khai nên là một Orchestrator chính, gọi các tools/model rõ ràng phía sau, thay vì nhiều agent tự trị khó debug.

## 1. Design Principle

Agent trong GreenFlow là **control copilot có guardrails**, không phải agent tự do.

Agent phải ra quyết định dựa trên:

```text
current_state
+ building_graph
+ prediction
+ simulation_result
+ policy
+ action_history
```

LLM được dùng để điều phối, giải thích và tương tác với người dùng. Các quyết định safety, policy và write action không nên để LLM tự quyết bằng prompt thuần.

## 2. MVP Architecture

```text
User / Dashboard Event
        ↓
Orchestrator Agent
        ↓
State Reader
Building Graph Tool
Forecast Tool
Simulation Tool
Policy Tool
Action Planner
Audit Logger
        ↓
Recommendation / Auto Action / Human Approval
```

MVP nên có:

- `Orchestrator Agent`
- `Building Graph Tool`
- `Forecast Tool`
- `Simulation Tool`
- `Policy Tool`
- `Action Logger`

Chưa cần nhiều autonomous agents chạy song song. Một orchestrator mạnh, gọi tools rõ ràng, sẽ dễ kiểm thử, dễ demo và dễ giải thích hơn.

## 3. Orchestrator Agent

Orchestrator là agent chính và user-facing.

Nhiệm vụ:

- Đọc state hiện tại của tòa nhà.
- Hiểu user command hoặc dashboard event.
- Gọi graph query để biết quan hệ zone/device/camera/meter.
- Gọi forecast model để lấy risk tương lai.
- Gọi simulation để kiểm tra candidate action.
- Gọi policy tool để quyết định auto/approval/reject.
- Tạo explanation cho facility manager.
- Ghi audit log.

Ví dụ user hỏi:

```text
Tại sao tầng 4 đang tốn điện cao?
```

Orchestrator sẽ:

```text
read zone states
→ query graph xem tầng 4 có device nào
→ check occupancy
→ check energy anomaly
→ query action history
→ trả lời + đề xuất action
```

## 4. Building Graph Tool

Tool này xử lý semantic building graph. MVP có thể dùng Neo4j hoặc JSON graph trước, nhưng interface nên giữ ổn định.

Nhiệm vụ:

- Map `floor -> zone -> room -> device -> sensor -> camera`.
- Cho biết thiết bị nào phục vụ zone nào.
- Cho biết action target hợp lệ là gì.
- Cho biết zone/device nào critical, không được auto-control.

Output ví dụ:

```json
{
  "zone_id": "F04_MEETING_02",
  "served_by": ["FCU_044", "LIGHT_044"],
  "camera_id": "CAM_F04_02",
  "risk_level": "normal",
  "controllable_devices": ["FCU_044", "LIGHT_044"]
}
```

## 5. Forecast Tool

Forecast Tool gọi các model ML predict.

Nhiệm vụ:

- Dự đoán energy / HVAC load.
- Dự đoán zone temperature.
- Dự đoán cost.
- Dự đoán comfort risk.
- Dự đoán peak risk.

Input:

```text
zone_state + weather + occupancy + setpoint + time_features
```

Output ví dụ:

```json
{
  "horizon_minutes": 120,
  "predicted_energy_kwh": 18.4,
  "predicted_temp_c": 25.8,
  "comfort_risk": "low",
  "peak_risk": "medium",
  "confidence": 0.82
}
```

## 6. Simulation Tool

Simulation Tool gọi EnergyPlus hoặc simulator nhẹ.

Nhiệm vụ:

- So sánh baseline vs candidate action.
- Ước lượng tác động của action.
- Kiểm tra action có phá comfort không.
- Trả về KPI cho dashboard và approval queue.

Input:

```text
current_state + candidate_action + weather + occupancy + schedule
```

Output ví dụ:

```json
{
  "baseline_energy_kwh": 24.2,
  "candidate_energy_kwh": 20.1,
  "energy_saved_kwh": 4.1,
  "cost_saved_vnd": 12300,
  "comfort_violation_minutes": 0,
  "verdict": "safe"
}
```

## 7. Policy Tool

Policy Tool phải là deterministic rule engine, không phải LLM-only logic.

Nhiệm vụ:

- Xác định action có được auto-run không.
- Chặn action nguy hiểm.
- Xác định action nào cần human approval.
- Kiểm tra allowlist/denylist zone/device.
- Kiểm tra guardrails như confidence, setpoint delta, comfort risk.

Policy ví dụ:

```yaml
auto_allowed:
  - lighting_reduction
  - hvac_eco_mode

blocked_zones:
  - server_room
  - electrical_room

max_setpoint_delta_c: 1.5
min_occupancy_confidence: 0.8
```

Decision:

```text
low-risk + pass guardrails -> auto action
medium-risk -> approval queue
high-risk -> simulation only / recommendation only
```

## 8. Action Planner

Action Planner tạo candidate actions theo schema chuẩn.

Action schema:

```json
{
  "action_type": "hvac_setback",
  "target_zone_id": "F04_MEETING_02",
  "target_device_ids": ["FCU_044"],
  "parameters": {
    "setpoint_delta_c": 1.5,
    "duration_minutes": 60
  },
  "reason": "Zone empty for 20 minutes with high occupancy confidence",
  "risk_level": "low"
}
```

Action types nên hỗ trợ:

- `lighting_reduction`
- `hvac_eco_mode`
- `hvac_setback`
- `pre_cooling`
- `early_shutdown`
- `ventilation_adjustment`
- `anomaly_alert`
- `maintenance_ticket`

## 9. Decision Loop

Luồng chuẩn của agent:

```text
1. Read current state
2. Detect issue or receive user command
3. Query building graph
4. Run forecast
5. Generate candidate actions
6. Simulate candidate actions
7. Check policy
8. Decide auto / approval / reject
9. Write audit log
10. Update dashboard
```

## 10. Agent State

Agent không nên nhớ state bằng conversation memory. State phải nằm trong database.

Nên lưu:

- current building state,
- latest forecasts,
- active alerts,
- proposed actions,
- executed actions,
- rejected actions,
- user policies,
- operator feedback,
- simulation results.

Không nên lưu mọi thứ vào LLM memory. LLM chỉ đọc context cần thiết từ DB/tools.

## 11. Recommendation Output

Mỗi recommendation nên có cấu trúc:

```json
{
  "title": "Set meeting room F04-02 to eco mode",
  "action_type": "hvac_eco_mode",
  "expected_energy_saving_kwh": 4.1,
  "expected_cost_saving_vnd": 12300,
  "comfort_risk": "low",
  "confidence": 0.82,
  "decision_mode": "auto",
  "explanation": "The room has been empty for 20 minutes and predicted temperature remains within comfort bounds.",
  "simulation_id": "sim_20260609_001"
}
```

## 12. Audit Log Requirements

Mỗi action phải tạo audit record.

Audit fields:

- `action_id`
- `timestamp`
- `agent_id`
- `action_type`
- `target_zone_ids`
- `target_device_ids`
- `trigger_state`
- `expected_saving_kwh`
- `expected_cost_saving`
- `comfort_risk_before`
- `comfort_risk_after`
- `confidence`
- `decision_mode`
- `policy_rule_id`
- `status`
- `explanation`

## 13. Why This Design

Thiết kế này giữ agent đủ thông minh để pitch là agentic AI, nhưng vẫn đủ kiểm soát để trả lời các câu hỏi về safety.

Mapping vai trò:

- LLM: orchestration, explanation, user interaction.
- ML model: prediction.
- EnergyPlus: physical simulation.
- Rule engine: policy and safety.
- Graph DB: building semantics.
- Database: source of truth.
- Human-in-the-loop: approval cho action rủi ro.

