# GreenFlow — Zone: phân cấp & tổng hợp (cha → con) trên toàn hệ

> Giải thích cách "zone" được chia ở Dashboard-3D, bảng web và Electrical-3D, và vì sao
> **số zone khác nhau**. Viết **đúng theo code + data thật đã kiểm chứng** (đã sửa bản nháp trước).

---

## 0. TL;DR — chỉ có **MỘT mô hình vật lý**, xem ở **2 độ mịn**

Gốc vật lý chung: **ARCH IFC IfcSpaces = 308 không gian** trên **10 storey thật**, khoá gốc = `IfcSpace.GlobalId`.

| | **Operational (Dashboard 3D + bảng + agent)** | **Electrical (trang /electrical + graph)** |
|---|---|---|
| Số zone | **14** (subset đại diện) | **308** (đầy đủ) |
| ID zone | `zone_<GUID>` | `tz_<GUID>` |
| Tầng | **10 storey ARCH thật** (level_01…) | **10 storey ARCH thật** |
| Tên/room_type | thật, từ IFC (Open Office 220, Lobby 100…) | thật, từ IFC |
| Nguồn | `db/seed/normalized_building.json` (do `build_3d_assets.py` sinh từ IFC) | ARCH IFC + gold E+ `openmeteo_2025_30min` |
| Telemetry | E+ thật cả năm (`scripts/load_real_data.py` → `telemetry_zone_15m`) | gold Parquet |

> **Vì sao bạn thấy khác:** chỉ là **cùng toà nhà, cùng 10 tầng, cùng GUID — khác độ mịn**
> (Dashboard dùng **14 zone đại diện**, Electrical dùng cả **308**) và khác prefix
> (`zone_` ↔ `tz_`). **14 zone là tập con 1:1 của 308** (đã kiểm: 14/14 khớp `tz_<cùng GUID>`).
> KHÔNG phải 3 mô hình rời rạc.

---

## 1. Lớp Operational — 14 zone (Dashboard + bảng "Zone state" + agent)

### Phân cấp cha → con
```
Building (greenflow_archetype)
└─ Floor × 10  (storey ARCH thật: sea_level · foundation · basement · level_01 ·
                level_02a_parking · level_02 · level_03 · level_04 · level_05 · roof)
   └─ Zone × 14  (= IfcSpace đại diện)   entity_key = zone_<GUID>
      vd: zone_3xtnrBUgHBCwRh_xfyB8zE  "Lobby 100"  (lobby, level_01)
          zone_..._xfyB4IZ            "Open Office 220" (open_office, level_02)
      └─ Room(s) → Device × 3/zone: airterminal / lighting / plug
```
- Nguồn seed: [seed_demo.py](../scripts/seed_demo.py) đọc **[db/seed/normalized_building.json](../db/seed/normalized_building.json)**
  (14 zones, do [build_3d_assets.py](../scripts/build_3d_assets.py) trích từ IFC) → bảng Postgres `zones`.
- ID: `entity_key = "zone_" + <IfcSpace.GUID>`; `room_type` + tên thật từ IFC; `floor_key` = storey thật.
- Telemetry thật: [load_real_data.py](../scripts/load_real_data.py) nạp E+ cả năm vào `telemetry_zone_15m`,
  khớp **`zone_<guid>` ↔ `tz_<guid>`** (chỉ đổi prefix) — docstring: *"14 zone demo khớp 1:1 (zone_<x> ↔ tz_<x>)"*.

### Bảng "Zone state" lấy zone CHÍNH XÁC như thế nào
```
ZoneStateTable.tsx  ← api.zones()  →  GET /api/zones
  • db_tool.get_zones(building):  SELECT id,name,entity_key,room_type,area,floor_id,floor_name
                                  FROM zones ORDER BY name           → cột Zone + Type
  • db_tool.get_latest_zone_state: SELECT DISTINCT ON(zone_id) … FROM telemetry_zone_15m
                                  tại REPLAY ANCHOR "now" (KHÔNG max timestamp)
                                  → Occupancy, Temp, Load(total_power_kw), Comfort, Peak
```
- **Zone (tên) + Type (room_type)** = tĩnh, từ bảng `zones` (14 IfcSpace).
- **5 cột state** = telemetry E+ phát lại tại mốc "now" (ngày hè đã ghim, không phải cuối năm).
  Trong đó **power/temp/RH** là E+ mô phỏng; **occupancy/CO₂/comfort/peak** là **suy ra**
  (occupancy = hồ sơ giờ làm việc × diện tích × mật độ room_type; comfort_risk = temp>26.5 khi có người;
  peak_risk = tải toà nhà / đỉnh năm — xem `load_real_data.py`).
- Bảng hiện ~14 hàng vì **DB chỉ có 14 zone** (`get_zones` không LIMIT, ORDER BY name).

---

## 2. Lớp Electrical — 308 zone (trang /electrical + graph)

### Phân cấp cha → con
```
Building
└─ Floor × 10 (cùng 10 storey ARCH)
   └─ ThermalZone × 308 (= IfcSpace, bbox thật)   zone_id = tz_<GUID>
      ├─ eplus_zone_name  (đồng nhất 1:1 EnergyPlusZone — confidence exact)
      ├─ room_type (8 loại)
      └─ LoadPoint → Circuit → Board
```
- Nguồn: ARCH IFC (308 IfcSpace) + gold E+ (308 zone, 30 phút, cả năm). ID `tz_+sanitize(GUID)`.
- Build: [electrical/spatial_map.py](../backend/greenflow/electrical/spatial_map.py), [scene.py](../backend/greenflow/electrical/scene.py).

### Thống kê 308 zone
- **room_type:** office **219** · meeting_room 29 · utility 22 · circulation 14 · open_office 11 · amenity 7 · hallway 5 · lobby 1.
- **theo tầng:** level_01 **60** · level_03 59 · level_04 59 · level_02 53 · basement 52 · level_05 24 · foundation 1 (zone ở 7/10 storey).

---

## 3. Quan hệ 14 ↔ 308 (cùng GUID, khác prefix)

```
operational  zone_<GUID>   ──(đổi prefix zone_→tz_)──▶   electrical  tz_<GUID>
14 zone đại diện            ⊂  (tập con 1:1, đã kiểm 14/14)        308 zone đầy đủ
```
Ví dụ đã kiểm: `zone_3jzuKaCoj7duM8YUpx6IdZ` (Postgres) ↔ `tz_3jzuKaCoj7duM8YUpx6Id…` = *ZN_0014* (amenity, level_01).
→ Click cùng một phòng ở Dashboard và Electrical **là cùng IfcSpace**, chỉ khác ID-prefix và việc Dashboard chỉ nạp 14/308.

---

## 4. Bảng đối chiếu khoá zone qua các lớp

| Lớp | Khoá zone | Ví dụ | Tầng |
|---|---|---|---|
| IFC ARCH (gốc) | `IfcSpace.GlobalId` | `3jzuKaCoj7duM8YUpx6IdZ` | IfcBuildingStorey |
| EnergyPlus gold | `zone_id` / `eplus_zone_name` | `tz_3jzu…` / `ZN_0014_…` | `floor_id` NULL → suy từ ARCH |
| Electrical KG (308) | ThermalZone `node_id` | `tz_3jzu…` | `floor_level_01` |
| **Operational (14)** | `entity_key` | `zone_3jzu…` | `level_01` (storey thật) |
| 3D XKT viewer | `xeokit_object_id` ↔ `mesh_entity_map.entity_key` | (metadata) | — |

---

## 5. Các loader KHÁC trong code (KHÔNG chạy ở deploy này — tránh nhầm)

- [load_real_into_demo.py](../scripts/load_real_into_demo.py): gộp về **5 archetype phẳng** `zone_storey0_{open_office,office,meeting,amenity,circulation}` (xây trên IDF demo 5-zone `greenflow_archetype.idf` + `bim/normalized.py`). Đây là **đường cũ**; nếu chạy nó thì bảng sẽ chỉ có 5 zone — KHÁC hiện trạng 14 của bạn.
- [load_real_telemetry.py](../scripts/load_real_telemetry.py): **188 zone** (lần chạy E+ Jun–Aug 2025) — tập/lần chạy khác 308 (openmeteo cả năm). Cũng không phải deploy hiện tại.
- `data/greenflow_archetype.idf` = **5 ZONE** (legacy); `data/IDF_FILE.idf` = **308 ZONE** (cái electrical dùng).

---

## 6. Map code ↔ data

| Thành phần | File | Dữ liệu |
|---|---|---|
| Zones operational (14) | `scripts/seed_demo.py` ← `scripts/build_3d_assets.py` | `db/seed/normalized_building.json`, Postgres `zones` |
| Telemetry thật (14) | `scripts/load_real_data.py` | `telemetry_zone_15m` (gold DuckDB) |
| Zones electrical (308) | `electrical/spatial_map.py`, `scene.py`, `graph_build.py` | `data/.../mapping/zones.csv`, `space_boxes.csv`, `graph_nodes.csv` |
| API bảng | `api/routers/buildings.py` `/zones`, `agent/tools/db_tool.py` | Postgres |
| Schema | `db/schema.sql` (`zones,rooms,floors,mesh_entity_map`) | Postgres |
| Loader thay thế | `load_real_into_demo.py` (5) · `load_real_telemetry.py` (188) | — |

---

## 7. Insight & khuyến nghị

- **Tin tốt:** Operational và Electrical **không xung đột** — cùng IfcSpace/GUID/10 tầng. Dashboard chỉ dùng
  **14 zone đại diện** (1 vài/loại/tầng) cho realtime gọn; Electrical dùng **308** đầy đủ. Hoà giải bằng
  **đổi prefix `zone_`↔`tz_`**.
- **Vì sao khác số:** chủ đích — demo operational chạy lần E+ 14-zone (nhẹ, mượt); engineering cần toàn bộ 308.
- **Nếu muốn liền mạch hai chiều:** thêm cột `arch_guid` (bỏ prefix) vào cả hai, hoặc view ánh xạ
  `zone_<g> ↔ tz_<g>` → click zone ở Electrical-3D nhảy đúng hàng bảng/ô 3D Dashboard và ngược lại.
- **Nhãn UI nên ghi rõ:** Dashboard *"14 không gian đại diện"*, Electrical *"308 không gian IFC"* — để khỏi tưởng là hai toà nhà khác nhau.

---

## 8. Một câu

> Toàn hệ chỉ có **một toà nhà, một bộ 308 IfcSpace trên 10 storey thật**. Dashboard/bảng hiển thị
> **14 không gian đại diện** (`zone_<GUID>`, tên/room_type/tầng thật, telemetry E+ phát lại); Electrical
> hiển thị **toàn bộ 308** (`tz_<GUID>`). **14 ⊂ 308, khớp 1:1 theo GUID** — khác nhau chỉ là **độ mịn +
> prefix**, không phải mô hình rời rạc. (5-archetype và 188 chỉ là loader cũ/thay thế, không chạy ở deploy này.)
