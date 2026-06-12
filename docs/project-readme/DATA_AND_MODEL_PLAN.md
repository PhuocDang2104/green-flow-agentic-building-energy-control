# Data and Model Plan

Tài liệu này mô tả kế hoạch data và model cho MVP. Đây là plan làm rõ trước khi triển khai, chưa phải schema/code cuối cùng.

## Data Sources

| Source | MVP approach | Output chính |
|--------|--------------|--------------|
| BIM4LCA ARCH.zip | Extract mô hình kiến trúc từ IFC/Revit/Archicad/specs | floor plan, room layout, space, area, envelope, materials |
| BIM4LCA STRUCTURAL.zip | Extract mô hình kết cấu từ Tekla/IFC/specs | columns, beams, slabs, walls, structure materials, quantities |
| BIM4LCA HVAC.zip | Extract MEP/HVAC/electrical từ Magicad/Revit/IFC/specs | HVAC equipment, ducts/pipes, electrical systems, sprinkler, equipment-zone map |
| Edge devices | Kết hợp input có sẵn và mock telemetry | device state, power, setpoint, temperature, humidity |
| CCTV | Video public để demo YOLO | occupancy count, occupied/unoccupied, confidence |
| Weather | API thật, ưu tiên Open-Meteo | outdoor temp, humidity, precipitation, solar/cloud, forecast |
| Utility tariff | User cấu hình | electricity price, water price, peak/off-peak rate |
| Schedule | Mock hoặc config | working hours, room booking, holiday |
| Building metadata | Config ban đầu | floor, zone, room type, equipment map |

## BIM4LCA Data Source Plan

GreenFlow có thể dùng 3 file zip BIM4LCA như nguồn building context chính. Đây là lợi thế lớn vì hệ thống không phải tự vẽ toàn bộ tòa nhà hoặc tự tạo zone/equipment mapping từ đầu.

### ARCH.zip: architecture model

Use cases:

- Lấy layout phòng, mặt bằng, không gian và diện tích.
- Xây dựng floor/zone/room hierarchy cho dashboard 3D.
- Lấy vật liệu kiến trúc, tường, sàn, mái, cửa, facade, shading.
- Tạo geometry tổng thể cho digital twin hoặc schematic 3D model.
- Hỗ trợ energy simulation features như envelope, glazing, shading và material thermal proxy.

MVP output nên extract:

- `floor`
- `space/room`
- `zone`
- `area_m2`
- `room_type`
- `geometry/bounding box`
- `wall/window/door/facade summary`
- `material summary`

### STRUCTURAL.zip: structural model

Use cases:

- Lấy hệ kết cấu chính: cột, dầm, sàn, tường chịu lực, móng.
- Lấy vật liệu kết cấu gỗ/bê tông và khối lượng cấu kiện.
- Phục vụ LCA/material reporting nếu pitch mở rộng sang carbon.
- Bổ sung constraint geometry cho 3D model.

MVP output nên extract:

- `structural_element`
- `element_type`
- `material`
- `quantity/volume`
- `floor/zone association if available`

GreenFlow HVAC optimization không cần STRUCTURAL làm nguồn P0, nhưng nên ghi nhận để mở rộng ESG/LCA story.

### HVAC.zip: MEP/HVAC/electrical model

Use cases:

- Lấy hệ thống thông gió, sưởi/làm mát, đường ống, thiết bị HVAC.
- Lấy electrical equipment và sprinkler context.
- Xây dựng zone-equipment mapping cho agent.
- Tạo mock edge device telemetry sát với BIM hơn.
- Tạo action target thật hơn: fan coil/AHU/VAV/damper/lighting/electrical panel.

MVP output nên extract:

- `hvac_equipment`
- `equipment_type`
- `served_zone`
- `duct/pipe relation`
- `electrical_device`
- `rated_capacity if available`
- `controllable flag`
- `risk_level`

Đây là zip quan trọng nhất cho GreenFlow nếu mục tiêu là AI HVAC optimization, energy simulation và operation-data generation.

## BIM to GreenFlow Mapping

```text
ARCH.zip
-> floor / room / space / area / envelope
-> dashboard 3D + zone hierarchy

STRUCTURAL.zip
-> structure elements / material quantities
-> LCA and carbon extension

HVAC.zip
-> HVAC/electrical devices / MEP relations
-> semantic graph + mock edge telemetry + agent action targets
```

Recommended extraction priority:

1. IFC files, vì dễ parse bằng IfcOpenShell và giữ semantic object types.
2. Specifications/material schedules, vì có thể chứa metadata sạch hơn model geometry.
3. Native Revit/Archicad/Tekla/Magicad files, nếu team có tool export phù hợp.

## Building Data Model

MVP nên dùng building lớn dạng configurable:

- `building`: id, name, location, timezone.
- `floor`: id, level, name.
- `zone`: id, floor_id, type, area_m2, comfort profile.
- `room`: id, zone_id, room_type, capacity.
- `device`: id, zone_id, type, controllable, risk_level.
- `meter`: id, zone_id/building_id, metric.
- `camera`: id, zone_id, video_source, privacy_mode.
- `tariff`: electricity/water unit price, peak/off-peak periods.

## Telemetry Schema Draft

### Zone state

| Field | Meaning |
|-------|---------|
| `timestamp` | Mock realtime timestamp |
| `zone_id` | Zone identifier |
| `occupancy_count` | Number of detected people |
| `occupancy_state` | empty, low, normal, high |
| `occupancy_confidence` | Confidence from YOLO aggregation |
| `temperature_c` | Zone temperature |
| `humidity_pct` | Zone humidity |
| `co2_ppm` | Optional IAQ proxy |
| `hvac_power_kw` | HVAC energy draw |
| `lighting_power_kw` | Lighting energy draw |
| `total_power_kw` | Combined zone power |
| `comfort_risk` | low, medium, high |
| `cost_vnd_per_hour` | Estimated hourly cost |

### Device state

| Field | Meaning |
|-------|---------|
| `device_id` | Device identifier |
| `zone_id` | Zone mapping |
| `device_type` | hvac, lighting, meter, sensor |
| `status` | on, off, eco, fault, standby |
| `setpoint_c` | HVAC setpoint if applicable |
| `power_kw` | Current power |
| `controllable` | Whether agent can act |
| `last_action_id` | Latest action affecting device |

## CCTV Occupancy Pipeline

MVP flow:

```text
Public demo video
-> YOLO person detection
-> frame-level people count
-> zone-level aggregation
-> occupancy_count / state / confidence
-> dashboard + forecast features + agent state
```

Privacy framing:

- Không nhận diện khuôn mặt.
- Không cần lưu raw video trong MVP.
- Chỉ dùng count/state/confidence theo zone.
- Video public dùng cho demo, không phải dữ liệu nhạy cảm.

## Weather Pipeline

Weather API nên lấy theo location của tòa nhà:

- Current weather cho dashboard.
- Forecast vài giờ tới cho model/agent.
- Historical hoặc replay weather cho training/demo.

Recommended fields:

- Outdoor temperature.
- Relative humidity.
- Cloud cover hoặc solar radiation nếu có.
- Precipitation/rain.
- Wind speed optional.

## Utility Cost Model

MVP bắt đầu bằng cấu hình đơn giản:

```text
electricity_cost = energy_kwh * tariff_vnd_per_kwh
water_cost = water_m3 * tariff_vnd_per_m3
```

Sau đó mở rộng:

- Peak/off-peak tariff.
- Demand charge.
- CO2 emission factor.
- Cost by floor/zone/device.

## Model Targets To Research and Confirm

Team muốn build model từ đầu, nhưng cần chốt target theo mức độ demo và dữ liệu.

### Recommended MVP targets

| Priority | Target | Why it matters |
|----------|--------|----------------|
| P0 | Zone/building energy forecast | Chứng minh tiết kiệm năng lượng |
| P0 | Zone temperature forecast | Kiểm tra comfort risk |
| P0 | Cost forecast | Dễ pitch với business impact |
| P1 | Comfort violation risk | Cho action safety check |
| P1 | Peak demand risk | Cho heatwave/peak-price scenario |
| P1 | Occupancy forecast | Tăng chất lượng pre-cooling/setback |
| P2 | Equipment anomaly score | Tạo alert và maintenance story |

## Proposed Model Stack

### Occupancy model

- YOLO person detection.
- Output không phải identity, chỉ là count/state/confidence.
- Đánh giá bằng manual counting trên một vài đoạn video demo.

### Forecast model

Start simple:

- LightGBM/XGBoost/RandomForest hoặc Ridge baseline.
- Input: weather, time features, zone type, occupancy, setpoint, historical power/temp.
- Output: energy/load, temperature, cost.

Then improve:

- LSTM/TFT nếu có đủ sequence data.
- Multi-output model nếu muốn forecast nhiều target cùng lúc.

### Comfort risk model

MVP có thể bắt đầu bằng hybrid model:

- Dự đoán temperature.
- So với comfort threshold theo zone type.
- Risk = probability/score of threshold violation.

### Anomaly model

Start with rules:

- HVAC power cao khi occupancy bằng 0.
- Lighting bật ngoài giờ.
- Temperature không giảm dù HVAC chạy.
- Power vượt baseline theo weather/occupancy.

Then improve:

- Isolation Forest hoặc autoencoder nếu có đủ data.

## Evaluation Metrics

| Model | Metrics |
|-------|---------|
| Energy forecast | MAE, RMSE, MAPE |
| Temperature forecast | MAE, comfort threshold violation error |
| Cost forecast | MAE/MAPE |
| Occupancy count | count MAE, occupied/unoccupied accuracy |
| Comfort risk | precision/recall hoặc confusion matrix |
| Anomaly | precision/recall trên labeled/mock scenarios |

## Data Split Plan

Cho demo:

- Train trên historical/mock replay.
- Validate trên holdout timeline.
- Export last-day hoặc selected scenario cho frontend simulation.

Không shuffle time-series data khi evaluate forecasting.

## Open Questions Before Build

1. Chốt model target P0: energy + temperature + cost có đủ chưa?
2. Có cần forecast theo từng zone hay toàn building trước?
3. Có dùng HOT/EnergyPlus làm data nền hay tự generate building-scale dataset?
4. YOLO output cần map vào bao nhiêu camera/zone trong demo?
5. Comfort threshold dùng chuẩn chung hay tự cấu hình theo room type?
