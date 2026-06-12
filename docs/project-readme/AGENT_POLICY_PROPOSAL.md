# Agent Policy Proposal

Tài liệu này là proposal policy để team duyệt trước khi implement. Mục tiêu là cho phép agent tự động xử lý action low-risk đã được người dùng cấu hình, trong khi action có rủi ro cao vẫn cần human approval.

## Policy Principles

Agent không được tự ý tối ưu bằng mọi giá. Mỗi action phải cân bằng:

- Energy saving.
- Cost saving.
- Comfort risk.
- Occupancy confidence.
- Device risk level.
- User-defined rules.
- Auditability.

## Action Risk Levels

### Low-risk: eligible for auto-action

Agent có thể tự động thực hiện nếu policy được bật và điều kiện an toàn thỏa mãn.

| Action | Condition draft | Safety guard |
|--------|-----------------|--------------|
| Lighting reduction | Zone empty trong `N` phút | Occupancy confidence >= threshold |
| Turn off non-critical lighting | Zone empty ngoài giờ làm việc | Không áp dụng emergency/common safety lighting |
| HVAC eco mode nhẹ | Zone empty/low occupancy trong `N` phút | Setpoint change <= configured limit |
| HVAC setback nhẹ | Occupancy thấp và comfort risk low | Không vượt comfort threshold |
| Alert anomaly | HVAC/lighting chạy bất thường | Chỉ tạo alert/ticket, không tắt thiết bị critical |
| Reminder action | Thiết bị chạy ngoài lịch | Notification only |

### Medium-risk: approval required by default

| Action | Why approval is needed |
|--------|------------------------|
| Pre-cooling trước peak hour | Có thể tăng energy ngắn hạn nếu forecast sai |
| Dynamic setpoint nhiều zone | Ảnh hưởng comfort nhiều người |
| Early HVAC shutdown | Có thể gây nóng/cuối ngày vẫn có người |
| Ventilation reduction | Có thể ảnh hưởng IAQ |
| Floor-level eco mode | Phạm vi rộng hơn một zone |

### High-risk: simulation/recommendation only in MVP

| Action | MVP behavior |
|--------|--------------|
| Whole-building HVAC shutdown | Chỉ simulate/recommend |
| Override critical/server/utility room | Không auto |
| Strong ventilation reduction | Không auto |
| Demand-response aggressive curtailment | Chỉ simulate và cần approval |
| Action khi occupancy confidence thấp | Không auto |

## Suggested User Config

User có thể cấu hình policy theo dạng đơn giản trước:

```yaml
auto_actions:
  enabled: true
  max_setpoint_delta_c: 1.5
  min_occupancy_confidence: 0.8
  empty_zone_delay_minutes: 15
  allowed_zone_types:
    - open_office
    - meeting_room
    - hallway
  blocked_zone_types:
    - server_room
    - electrical_room
    - security_room
  allowed_actions:
    - lighting_reduction
    - hvac_eco_mode
    - anomaly_alert
approval_required:
  - pre_cooling
  - floor_level_setback
  - ventilation_adjustment
  - early_shutdown
```

## Auto-Action Decision Logic

Draft logic:

```text
1. Agent generates candidate action.
2. Check if action type is allowed for auto-action.
3. Check zone/device is not blocked.
4. Check occupancy confidence.
5. Check predicted comfort risk after action.
6. Check max setpoint/power change limit.
7. Run lightweight simulation if needed.
8. If all checks pass: execute mock action and log.
9. Otherwise: move to approval queue.
```

## Required Audit Fields

Every action should create an audit record:

| Field | Meaning |
|-------|---------|
| `action_id` | Unique action id |
| `timestamp` | Created/executed time |
| `agent_id` | Orchestrator/control agent |
| `action_type` | lighting_reduction, hvac_setback, pre_cooling, etc. |
| `target_zone_ids` | Affected zones |
| `target_device_ids` | Affected devices |
| `trigger_state` | Occupancy, weather, power, comfort at decision time |
| `expected_saving_kwh` | Estimated energy saving |
| `expected_cost_saving` | Estimated money saving |
| `comfort_risk_before` | Risk before action |
| `comfort_risk_after` | Risk after action |
| `confidence` | Agent/model confidence |
| `decision_mode` | auto, approval_required, rejected |
| `policy_rule_id` | Rule that allowed/blocked action |
| `status` | proposed, scheduled, executed, cancelled, failed |
| `explanation` | Human-readable reason |

## Proposed Default Rules

### Rule A: Empty meeting room lighting

If a meeting room has occupancy count = 0 for 15 minutes with confidence >= 0.85, reduce lighting or turn off non-critical lighting.

Decision mode: auto.

### Rule B: Empty zone HVAC eco mode

If an open office zone has occupancy state empty/low for 20 minutes, comfort risk is low, and predicted temperature stays inside threshold for 60 minutes, set HVAC to eco mode with max setpoint increase 1.5°C.

Decision mode: auto if enabled; otherwise approval.

### Rule C: Pre-cooling before hot/peak period

If weather forecast indicates heatwave or peak price period and occupancy forecast is high, simulate pre-cooling.

Decision mode: approval required.

### Rule D: HVAC running in empty zone

If HVAC power is high while occupancy is zero and schedule says unoccupied, create anomaly alert and recommend setback.

Decision mode: alert auto; control action approval unless policy allows low-risk eco mode.

### Rule E: Low confidence occupancy

If occupancy confidence < configured threshold, do not auto-change HVAC or lighting. Move to recommendation/approval.

Decision mode: blocked from auto.

## Questions For User Approval

1. Có cho auto lighting off ở meeting room khi zone empty không?
2. Max HVAC setpoint delta cho auto-action nên là 1°C, 1.5°C hay 2°C?
3. Auto-action có được chạy trong giờ làm việc không, hay chỉ sau giờ làm?
4. Zone nào tuyệt đối không được auto-control?
5. Có cần rollback tự động nếu comfort risk tăng sau action không?
