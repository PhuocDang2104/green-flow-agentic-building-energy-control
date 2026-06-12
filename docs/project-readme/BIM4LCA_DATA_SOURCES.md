# BIM4LCA Data Sources

GreenFlow có thể tận dụng 3 file zip từ BIM4LCA để xây dựng digital twin và semantic building graph. Đây là nền dữ liệu quan trọng để MVP không chỉ là dashboard mock, mà có bối cảnh tòa nhà, phòng, vật liệu và hệ HVAC/electrical cụ thể.

## 1. ARCH.zip: Architecture Model

`ARCH.zip` chứa mô hình kiến trúc của công trình ở nhiều định dạng như Archicad, Revit, IFC, specifications và thông tin materials-products.

### Data có thể lấy

- Layout phòng.
- Mặt bằng.
- Không gian/space.
- Diện tích phòng/zone.
- Vật liệu kiến trúc.
- Cửa, tường, sàn, mái.
- Facade, shading.
- Hình học tổng thể của công trình.

### GreenFlow use cases

- Tạo floor/zone/room hierarchy.
- Tạo 3D building model cho Tab 1.
- Gán room type cho từng khu vực.
- Tính area-based normalization, ví dụ kWh/m2.
- Tạo envelope/context features cho model energy nếu cần.
- Hỗ trợ story về building digital twin.

### MVP priority

P0 nếu cần tạo layout/digital twin từ BIM thật. Nếu thời gian gấp, có thể extract một phần rồi dùng schematic model.

## 2. STRUCTURAL.zip: Structural Model

`STRUCTURAL.zip` chứa mô hình kết cấu bằng Tekla Structures, IFC và specifications.

### Data có thể lấy

- Cột.
- Dầm.
- Sàn.
- Tường chịu lực.
- Móng.
- Vật liệu kết cấu như gỗ/bê tông.
- Khối lượng cấu kiện.
- Dữ liệu phục vụ LCA hoặc bóc tách vật liệu.

### GreenFlow use cases

- Bổ sung geometry/context cho digital twin.
- Mở rộng báo cáo LCA/carbon/material.
- Hỗ trợ pitch về lifecycle impact nếu cần.
- Tạo material quantity summary.

### MVP priority

P2 cho HVAC optimization. Không nên để STRUCTURAL làm blocker cho MVP, nhưng nên lưu trong roadmap vì liên quan tốt đến ESG/LCA narrative.

## 3. HVAC.zip: MEP/HVAC/Electrical Model

`HVAC.zip` chứa mô hình Magicad for Revit, IFC và specifications cho HVAC, sprinkler và electrical.

### Data có thể lấy

- Hệ thống thông gió.
- Hệ thống sưởi/làm mát.
- Đường ống/duct/pipe.
- Thiết bị HVAC.
- Thiết bị điện.
- Sprinkler.
- Quan hệ thiết bị với khu vực phục vụ, nếu model/spec có đủ metadata.

### GreenFlow use cases

- Xây dựng zone-equipment mapping.
- Tạo danh sách edge devices giả lập sát thực tế.
- Gán controllable devices cho agent.
- Xác định action target: HVAC setback, lighting reduction, ventilation change, anomaly alert.
- Tạo mock telemetry theo thiết bị thật trong BIM.
- Tăng độ thuyết phục cho Tab 2 Agent Actions.

### MVP priority

P0. Đây là nguồn dữ liệu quan trọng nhất nếu GreenFlow đi theo hướng AI HVAC optimization, energy simulation và agent control.

## Recommended Extraction Workflow

```text
1. Unzip BIM4LCA packages into local data/raw/bim4lca/
2. Inventory file formats and available IFC/spec files.
3. Parse IFC objects by type:
   - IfcBuildingStorey
   - IfcSpace
   - IfcZone
   - IfcWall / IfcSlab / IfcDoor / IfcWindow
   - HVAC/MEP/electrical object classes if available
4. Parse specifications/material schedules where IFC metadata is missing.
5. Normalize into GreenFlow schema:
   - floors.json
   - zones.json
   - rooms.json
   - devices.json
   - materials.json
   - zone_equipment_map.json
6. Generate mock telemetry based on extracted devices/zones.
7. Feed normalized data into dashboard, models, agent and simulation.
```

## Proposed Normalized Outputs

| Output | Source | Purpose |
|--------|--------|---------|
| `floors.json` | ARCH/IFC | Building navigation and 3D model |
| `rooms.json` | ARCH/IFC/specs | Room layout and room type |
| `zones.json` | ARCH/HVAC/specs | Operation units for dashboard/model/agent |
| `devices.json` | HVAC/specs | Edge device inventory |
| `zone_equipment_map.json` | HVAC + spatial relation | Agent action target mapping |
| `materials.json` | ARCH/STRUCTURAL/specs | LCA/material/carbon extension |
| `geometry_summary.json` | ARCH/STRUCTURAL IFC | 3D/schematic rendering |

## Questions Before Extraction

1. Ba zip hiện đang nằm ở đâu trong repo hoặc máy local?
2. Trong mỗi zip có file IFC không, hay chỉ native Revit/Archicad/Tekla/Magicad?
3. Team muốn 3D dashboard dựa trực tiếp trên BIM geometry, hay chỉ extract layout rồi render schematic building?
4. Có cần dùng STRUCTURAL cho pitch vòng này không, hay để trong extension/roadmap?
5. HVAC.zip có đủ metadata served zone/equipment name không, hay cần manual mapping?
