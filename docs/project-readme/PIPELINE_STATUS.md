# GreenFlow — Pipeline Status & Cách chạy (đã làm được gì)

> Tài liệu này ghi lại **những gì đã build + verify trên local**, các quyết định đã chốt, cấu trúc file, và cách chạy lại từ đầu. Cập nhật: 2026-06.

---

## 0. Tóm tắt trạng thái

Đã hoàn tất **đường dữ liệu end-to-end** (BIM → EnergyPlus thật → telemetry → kiểm chứng → feed model), chạy + verify trên local với **EnergyPlus 26.1.0**:

```
IFC (BIM)
 → extract + map thiết bị→zone (point-in-polygon)        [tools/bim_extractor.py]
 → sinh lịch input (occupancy/đèn/ổ cắm/setpoint)         [tools/datagen/]
 → EnergyPlus archetype (envelope QCVN, EPW Hà Nội)       [tools/idf/build_idf.py]
 → expand 5 archetype → 188 zone                          [tools/idf/expand_eplus.py]
 → telemetry zone + device 15' (physics = E+ thật)        [tools/datagen/pipeline.py]
 → kiểm chứng ý nghĩa + train surrogate                   [tools/verify_data.py]
```

**Kết quả verify:** dữ liệu nằm đúng khoảng vật lý (EUI 179 kWh/m²/năm, peak 76.6 W/m²), và surrogate LightGBM học lại E+ đạt **R² 0.95** → dữ liệu thật sự có nghĩa và feed được cho model.

---

## 1. Quyết định đã chốt

**Site & dữ liệu**
- Tòa nhà: `ARK_NordicLCA_Office_Concrete` — 10 tầng, 308 IfcSpace, **188 zone có người**, ~2.700 terminal phục vụ phòng.
- **Site = HÀ NỘI** (EPW `VNM_NVN_Hanoi-Noi.Bai.Intl.AP TMYx 2011-2025`). Khí hậu cận nhiệt: **hè nóng (T6 max 39°C), đông lạnh (T1 min 11°C → có heating)**.
- Window telemetry: **1/6–31/8** (mùa hè, heatwave/peak), 15 phút. E+ chạy **cả năm** để lấy EUI.

**3 nguyên tắc bất di bất dịch**
1. **E+ tính vật lý; nhóm chỉ tạo lịch.** Không bịa số nhiệt/điện.
2. **IFC đóng băng;** dữ liệu sống ở DB/parquet keyed theo zone/device id (raw_ifc_guid).
3. **Kiểm chứng action = chạy lại cùng ngày 2 lần** (baseline vs agent), không điều khiển E+ realtime.

**Envelope theo QCVN 09:2017** (xem mục 5).

**Stack:** PostgreSQL+pgvector, FastAPI, EnergyPlus 26.1, LightGBM, YOLO pretrained, Next.js+xeokit. Không Neo4j/Timescale/Redis ở P0.

---

## 2. Đã build & verify (theo file)

### 2.1. BIM extraction + device→zone mapping — `tools/bim_extractor.py`
- Trích floors/spaces/devices từ IFC.
- **Map thiết bị → phòng bằng point-in-polygon** (geometry IfcSpace world-coord qua `ifcopenshell.geom.iterator`).
- Sửa được các bẫy: unit mm/m, tên tầng Phần Lan↔Revit, loại phòng đa tầng/shaft.
- Output: `zone_equipment_map.json` — mỗi thiết bị gắn `scope` ∈ {zone, plant, floor}. ~3346/3358 thiết bị về đúng phòng; agent chỉ thao tác `scope=zone`.

### 2.2. Sinh dữ liệu — `tools/datagen/`
| File | Vai trò |
|---|---|
| `config.py` | Mọi tham số (window, lịch VN 2025, mật độ tải, setpoint, **envelope QCVN**, EPW Hà Nội) |
| `building.py` | Đọc zone từ `zone_equipment_map` (category, diện tích, terminal, đèn) |
| `calendar_vn.py` | Phân loại workday/weekend/lễ |
| `schedules.py` | **Lịch input** (chỉ thứ "bịa"): occupancy/đèn/ổ cắm/setpoint, seeded |
| `weather.py` | Đọc EPW Hà Nội thật (temp/RH/GHI) |
| `physics.py` | `load_eplus_zone_output()` (E+ thật) + `placeholder_rc` (dev, có warning) |
| `devices.py` | Phân bổ điện zone → từng terminal/đèn (edge actuator) |
| `sensors.py` | CO2 (cân bằng khối) + nhiễu/dropout cảm biến |
| `pipeline.py` | Ghép tất cả → parquet + KPI |

### 2.3. EnergyPlus archetype — `tools/idf/`
| File | Vai trò |
|---|---|
| `build_idf.py` | Dựng IDF: 5 archetype shoebox (geomeppy), envelope QCVN, IdealLoads + heat-recovery 0.5, thermostat dual (cool 24 / heat 20), People/Lights/Equip, Output 15' |
| `expand_eplus.py` | E+ output (5 archetype) → per-zone CSV (188 zone), scale năng lượng theo diện tích, dời timestamp về lưới datagen |

### 2.4. Kiểm chứng — `tools/verify_data.py`
Sanity vật lý + train surrogate LightGBM (split theo thời gian).

---

## 3. Cách chạy lại (local)

**Yêu cầu:** EnergyPlus 26.1 (`/Applications/EnergyPlus-26-1-0/`), Python libs:
```bash
pip install pandas numpy pyarrow lightgbm scikit-learn ifcopenshell shapely eppy geomeppy
```

**Chạy tuần tự (từ thư mục `tools/`):**
```bash
# (1) extract BIM + map thiết bị (nếu cần regen)
python bim_extractor.py

# (2) dựng IDF archetype
python -m idf.build_idf
#   -> idf/out/greenflow_archetype.idf + archetype_zone_map.json

# (3) chạy EnergyPlus (annual 15', EPW Hà Nội)
EPW="../Dataset/VNM_NVN_Hanoi-Noi.Bai.Intl.AP.488200_TMYx.2011-2025/VNM_NVN_Hanoi-Noi.Bai.Intl.AP.488200_TMYx.2011-2025.epw"
/usr/local/bin/energyplus -x -r -w "$EPW" -d idf/eprun idf/out/greenflow_archetype.idf

# (4) expand E+ → per-zone
python -m idf.expand_eplus
#   -> idf/out/zone_expanded.csv

# (5) sinh telemetry với physics E+ thật
python -m datagen.pipeline --eplus-csv idf/out/zone_expanded.csv --device-level demo
#   -> datagen/out/{zone_state,device_state,zone_sensor_edge,schedules}_15m.parquet

# (6) kiểm chứng + surrogate
python verify_data.py
```
> Bỏ `--eplus-csv` ở bước (5) sẽ dùng `placeholder_rc` (chạy được trước khi có E+, nhưng magnitude KHÔNG thật).

---

## 4. Kết quả kiểm chứng (đã đo)

**Ý nghĩa vật lý** (Jun–Aug, physics = E+):
| Chỉ số | Giá trị | Chuẩn |
|---|---|---|
| EUI | **179 kWh/m²/năm** | office 100–250 ✓ |
| Peak toàn nhà | 415 kW = **76.6 W/m²** | office 30–80 ✓ |
| Cơ cấu điện | HVAC **69%** / đèn 15% / ổ cắm 15% | hè cooling-dominated ✓ |
| Weekday / weekend | **2.3×** | ✓ |
| Occupancy ~ HVAC | corr **0.79** | ✓ |
| CO2 | mean 528 / p95 842 ppm | theo người ✓ |
| comfort_violation | 144.585 phút | chỉ khi có người + nóng ✓ |

**Feed cho model AI** (LightGBM surrogate, split theo thời gian, ~1.3M train / 332k test):
| Target | MAE | R² | Top features |
|---|---|---|---|
| HVAC power | 0.076 kW | **0.95** | outdoor_temp, area, giờ |
| Zone temp | 0.20 °C | **0.94** | outdoor_temp, giờ, category |

→ Telemetry, training, validation **cùng một thế giới E+** → không còn vòng lặp khép kín.

---

## 5. Tham số config chính (QCVN 09:2017 + đã chốt)

| Tham số | Giá trị | Nguồn |
|---|---|---|
| U tường ngoài | 1.79 W/m²K (R₀ 0.56) | QCVN 2.1.2 |
| U mái | 1.0 W/m²K (R₀ 1.0) | QCVN 2.1.2 |
| Kính SHGC / U | 0.52 / 2.8 W/m²K | QCVN Bảng 2.1 (WWR35 "Other") |
| WWR | 0.35 | chốt |
| LPD | 11 W/m² | QCVN Bảng 2.5 (office) |
| COP hệ thống | 3.5 | QCVN chiller≥4.5 trừ phụ trợ |
| Thu hồi nhiệt | 0.5 | QCVN 2.2.3(4) bắt buộc AC trung tâm |
| Setpoint cool/heat/setback | 24 / 20 / 28 °C | chốt |
| Gió tươi | 0.008 m³/s/người | ~ASHRAE 62.1 |
| Chiều cao trần | 3.5 m | chốt |

---

## 6. Chưa làm / bước tiếp

- [ ] Wrap surrogate → `ml/forecast_service.py` (bộ đoán nhanh cho agent).
- [ ] Sinh `world_run=agent` (nhúng action vào IDF) → so **baseline vs optimized**.
- [ ] `db/schema.sql` + nạp parquet vào Postgres (partition tháng, bulk COPY).
- [ ] Agent (LangGraph copilot + policy + regrettable_substitution_check).
- [ ] Frontend 3 tab + 3D viewer (xeokit).
- [ ] `--device-level all` cho mọi zone (chạy month-batch; cân nhắc Colab nếu RAM đuối).

## 7. Caveat
- **Placeholder physics** (`placeholder_rc`) chỉ để dev khi chưa có E+ — magnitude không thật, đừng pitch.
- **Climate mismatch (Plan B):** tái dùng hình học Nordic + EPW Hà Nội — **khai báo giả định này trong report**.
- Map thiết bị còn ~4% lệch tầng ở ranh giới sàn (convex hull) — nâng footprint thật là P2.
