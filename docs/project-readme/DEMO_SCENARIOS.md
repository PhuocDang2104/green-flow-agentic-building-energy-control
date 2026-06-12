# Demo Scenarios

Tài liệu này mô tả các kịch bản demo nên dùng để chứng minh GreenFlow hiệu quả.

## Demo Narrative

Pitch flow nên đi theo trình tự:

```text
1. Facility manager mở dashboard.
2. Thấy tòa nhà đang có một số zone tiêu thụ cao.
3. CCTV occupancy cho thấy vài zone gần như trống.
4. Forecast model dự đoán chi phí/peak risk tăng trong vài giờ tới.
5. Agent đề xuất action có giải thích và expected saving.
6. Simulation so sánh baseline vs optimized.
7. Manager approve action hoặc xem auto-action low-risk đã chạy.
8. Report hiển thị energy/cost saving và comfort vẫn an toàn.
```

## Scenario 1: Empty Zone Energy Waste

### Setup

- Một số meeting rooms/open office zones không có người.
- Lighting hoặc HVAC vẫn chạy theo fixed schedule.
- Occupancy confidence cao từ YOLO/mock aggregate.

### Agent action

- Auto lighting reduction.
- Recommend HVAC eco mode hoặc setback nhẹ.

### KPI

- Energy saved.
- Cost saved.
- Comfort risk unchanged.
- Number of unnecessary device runtime minutes reduced.

### Why it works for pitch

Kịch bản dễ hiểu, trực quan, phù hợp với occupancy-aware control.

## Scenario 2: Heatwave and Peak Demand

### Setup

- Weather API forecast outdoor temperature cao.
- Building occupancy dự kiến cao.
- Peak price hoặc peak demand risk tăng.

### Agent action

- Simulate pre-cooling.
- Dynamic setpoint adjustment.
- Approval required.

### KPI

- Peak demand reduction.
- Cost reduction during peak period.
- Comfort violation minutes.
- Predicted vs simulated load.

### Why it works for pitch

Liên kết trực tiếp với climate resilience và peak-grid stress.

## Scenario 3: After-Hours Operation

### Setup

- Sau giờ làm, một số tầng/zone vẫn có HVAC/lighting chạy.
- Schedule nói unoccupied.
- Occupancy từ camera thấp/empty.

### Agent action

- Auto anomaly alert.
- Recommend early shutdown hoặc floor-level setback.

### KPI

- After-hours runtime reduced.
- Cost saving.
- Audit log completeness.

### Why it works for pitch

Cho thấy GreenFlow giúp facility team giảm manual monitoring.

## Scenario 4: High Occupancy Meeting Event

### Setup

- Meeting room hoặc conference zone có occupancy cao bất thường.
- Temperature/CO2 proxy có nguy cơ tăng.

### Agent action

- Recommend maintaining/increasing cooling or ventilation.
- Avoid energy-saving action despite high cost.

### KPI

- Comfort/IAQ risk avoided.
- Explanation quality.
- Safety guardrail demonstration.

### Why it works for pitch

Chứng minh agent không chỉ tối ưu chi phí, mà biết bảo vệ comfort.

## Scenario 5: Equipment Anomaly

### Setup

- HVAC power cao nhưng temperature không cải thiện.
- Hoặc lighting/HVAC chạy khi zone empty.

### Agent action

- Create anomaly alert.
- Recommend maintenance ticket.
- Simulate expected waste if ignored.

### KPI

- Anomaly detected.
- Avoided energy waste estimate.
- Maintenance action created.

### Why it works for pitch

Thể hiện giá trị vận hành, không chỉ là dashboard đẹp.

## Suggested Pitch KPI Cards

- Total energy saved.
- Estimated cost saved.
- Peak demand reduction.
- Comfort violation minutes.
- Occupancy detection confidence.
- Forecast error.
- Agent actions executed.
- Actions pending approval.

## Demo Data Requirements

For each scenario, frontend cần có:

- Current zone states.
- Historical trend for baseline.
- Forecast output.
- Agent action list.
- Simulation comparison.
- KPI summary.

## Recommended MVP Demo Order

1. Dashboard overview.
2. Empty zone waste.
3. Agent auto-action low-risk.
4. Heatwave pre-cooling simulation.
5. Human approval.
6. Final savings report.
