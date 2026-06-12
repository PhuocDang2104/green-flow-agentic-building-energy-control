# GreenFlow Project Proposal

## One-Line Description

GreenFlow là nền tảng web agentic, simulation-first giúp quản lý tòa nhà văn phòng lớn tối ưu năng lượng, chi phí và comfort bằng dashboard 3D, occupancy từ CCTV, model dự đoán và AI agent có kiểm soát.

## Problem

Nhiều tòa nhà văn phòng vẫn vận hành HVAC và lighting bằng lịch cố định hoặc setpoint tĩnh. Cách vận hành này gây lãng phí năng lượng ở khu vực ít người, tăng chi phí điện, tạo peak load trong thời tiết nóng, làm mòn thiết bị và đôi khi vẫn không bảo vệ được comfort/indoor air quality ở các zone đông người.

Vấn đề không chỉ là giảm điện. Facility manager cần biết:

- Zone nào thật sự cần làm mát hoặc chiếu sáng.
- Action nào tiết kiệm mà không gây rủi ro comfort.
- Khi nào nên pre-cool, setback, shutdown hoặc cảnh báo anomaly.
- Tác động của action trước khi áp dụng vào vận hành.
- Vì sao AI đề xuất action đó và mức tin cậy là bao nhiêu.

## Proposed Solution

GreenFlow tạo một operations layer phía trên dữ liệu tòa nhà. Hệ thống thu thập và xử lý dữ liệu từ BIM4LCA models, edge devices, CCTV occupancy, weather API, schedule và cấu hình đơn giá. Dữ liệu BIM giúp tạo building context như layout phòng, zone, vật liệu và thiết bị HVAC/electrical; dữ liệu vận hành giúp tạo trạng thái realtime mock theo zone. Tất cả được chuyển thành trạng thái zone-level để dashboard, model ML và agent cùng sử dụng.

Trước khi action được áp dụng, GreenFlow chạy simulation để ước lượng tác động lên energy, cost, comfort và peak demand. Với action rủi ro thấp đã được cấu hình policy, agent có thể tự động thực hiện trong mock environment. Với action rủi ro trung bình/cao, hệ thống yêu cầu human approval.

## Target Users

| User group | Pain point | GreenFlow value |
|------------|------------|-----------------|
| Facility manager | Quá nhiều data rời rạc, khó biết zone nào đang lãng phí | Dashboard 3D, anomaly, action recommendation |
| Building owner | Chi phí điện cao, khó chứng minh hiệu quả tiết kiệm | Cost saving report, audit trail, KPI |
| ESG/energy team | Cần số liệu giảm phát thải có cơ sở | Energy/cost/CO2 avoided report |
| Occupants | Cần comfort ổn định | Comfort-aware control, tránh tiết kiệm cực đoan |
| Utility/city stakeholder | Peak load do cooling | Peak demand reduction, demand-flexibility scenario |

## Product Workflow

```text
1. Data ingestion
   Edge devices, CCTV video, weather API, schedule, utility tariff

2. Data processing
   Normalize telemetry, aggregate occupancy, map zone-equipment-camera-meter

3. Dashboard
   Facility manager xem trạng thái realtime mock của toàn tòa nhà

4. Prediction
   ML models dự đoán energy, temperature, cost, comfort/peak risk

5. Agent decision
   Orchestrator sinh recommendation hoặc action dựa trên state + policy + model

6. Simulation
   Kiểm chứng baseline vs optimized và dự đoán kịch bản tương lai

7. Approval / auto-action
   Human-in-the-loop cho action rủi ro; auto-action cho low-risk policy

8. Audit and reporting
   Lưu action, lý do, expected saving, confidence và kết quả
```

## Data Strategy

GreenFlow sẽ kết hợp data thật và data giả lập:

- BIM4LCA ARCH.zip: lấy layout phòng, mặt bằng, space, area, vật liệu kiến trúc, cửa/tường/sàn/mái/facade/shading và geometry tổng thể.
- BIM4LCA STRUCTURAL.zip: lấy cột, dầm, sàn, tường chịu lực, móng, vật liệu và khối lượng cấu kiện cho LCA/material extension.
- BIM4LCA HVAC.zip: lấy hệ HVAC/MEP/electrical/sprinkler, đường ống, thiết bị và zone-equipment mapping; đây là nguồn quan trọng nhất cho GreenFlow HVAC optimization.
- Edge devices: từ input/config sẽ sinh ra telemetry thiết bị như HVAC state, lighting state, power, temperature, humidity.
- CCTV occupancy: dùng video public để demo YOLO person detection, aggregate theo zone.
- Weather: dùng API thật, ưu tiên Open-Meteo vì dễ tích hợp và không cần API key cho nhiều use case.
- Utility cost: cấu hình đơn giá điện/nước, có thể thêm peak/off-peak tariff.
- Missing data: giả lập theo rule hoặc replay dataset để đảm bảo demo end-to-end.

## AI/ML Strategy

MVP sẽ build model thật ngay từ đầu nhưng giữ kiến trúc thực dụng:

- Occupancy model: YOLO person detection.
- Forecast model: dự đoán energy/load, zone temperature, cost và comfort/peak risk.
- Anomaly model: phát hiện bất thường như HVAC chạy khi zone trống hoặc energy vượt baseline.
- Simulation model: so sánh baseline fixed schedule với action agent đề xuất.

Model đầu tiên nên ưu tiên ML truyền thống như LightGBM/XGBoost/RandomForest cho tốc độ và explainability. Sau khi có pipeline ổn định, có thể mở rộng sang TFT/LSTM nếu dữ liệu đủ.

## Agent Strategy

Agent chính là Orchestrator. Nó không tự nghĩ rời rạc, mà dùng tool/model/policy:

- Đọc building state.
- Gọi semantic map để biết zone nào gắn với thiết bị/camera/meter nào.
- Gọi forecast model để biết rủi ro tương lai.
- Gọi simulation để kiểm tra candidate action.
- So policy để quyết định auto-action hay cần approval.
- Tạo explanation, confidence, expected saving và audit log.

## MVP Differentiation

GreenFlow khác dashboard năng lượng thông thường ở bốn điểm:

- Zone-level: nhìn theo khu vực, không chỉ tổng tòa nhà.
- Occupancy-aware: dùng CCTV people count thay vì lịch cố định.
- Simulation-first: kiểm chứng action trước khi áp dụng.
- Agentic workflow: AI điều phối prediction, policy, action và audit.

## Expected Impact

MVP cần chứng minh:

- Giảm energy/cost trong kịch bản zone ít người.
- Giảm peak demand trong kịch bản heatwave hoặc peak price.
- Giữ comfort violation trong ngưỡng chấp nhận.
- Agent action có trace rõ ràng và có thể phê duyệt/quản lý.

## Pitch Claim

GreenFlow giúp facility teams chuyển từ vận hành tòa nhà theo lịch cố định sang vận hành theo trạng thái thực, dự đoán tương lai và kiểm chứng bằng simulation, từ đó giảm chi phí năng lượng mà vẫn bảo vệ comfort và tính minh bạch trong quyết định.
