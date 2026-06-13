# GreenFlow — Parquet contract (đã verify với file thật, 2026-06-12)

Đây là contract giữa `tools/datagen` (producer) và `scripts/load_parquet_to_db.py`
(consumer). Schema dưới đây đọc trực tiếp từ parquet đã sinh — **không được đổi
tên/kiểu cột mà không sửa file này + schema.sql + loader cùng lúc.**

Quy ước chung:
- `timestamp`: `timestamp[ns]` **naive, local Asia/Ho_Chi_Minh**, lưới 15 phút,
  window `2025-06-01 00:00` → `2025-08-31 23:45` (8.832 step).
- `zone_id` / `device_id`: IFC GUID (text, 22 ký tự, có thể chứa `$`).
- 188 zone có người; device demo-level ~1.274 device (11,25M dòng).

## zone_state_15m.parquet  (1.660.416 dòng = 188 zone × 8.832 step)

| cột | kiểu | ghi chú |
|---|---|---|
| timestamp | timestamp[ns] | naive local |
| zone_id | string | IFC GUID |
| occupancy_count | int64 | |
| occupancy_frac | double | 0..1 so với design occupancy |
| occupancy_state | string | empty / low / normal / high |
| lighting_frac, plug_frac | double | schedule fraction |
| cooling_setpoint_c | double | |
| temperature_c, humidity_pct | double | ground truth E+ |
| cooling_thermal_kwh, cooling_thermal_kw | double | nhiệt, không phải điện |
| hvac_power_kw | double | điện HVAC (thermal / COP 3.5) |
| lighting_power_kw, plug_power_kw | double | |
| comfort_violation_min | double | phút violation trong step |
| comfort_risk | string | low / medium / high |
| source | string | 'eplus' (bắt buộc khi pitch) |
| co2_ppm | double | mass-balance |
| total_power_kw, energy_kwh | double | energy_kwh = total_power_kw × 0.25 |
| cost_vnd | double | tariff config.py (peak 3200 / offpeak 1800) |
| co2_kg | double | grid factor |
| scenario_id | string | 'normal_day' |
| world_run_id | string | 'baseline' |

## device_state_15m.parquet

| cột | kiểu | ghi chú |
|---|---|---|
| timestamp | timestamp[ns] | |
| device_id | string | IFC GUID |
| zone_id | string | |
| device_type | string | IfcAirTerminal, IfcLightFixture, ... |
| scope | string | zone / floor / plant — agent CHỈ thao tác scope=zone |
| status | string | |
| setpoint_c | double | |
| power_kw, energy_kwh | double | phân bổ từ zone xuống device |
| runtime_minutes | double | |
| fault_state | **null** | ⚠ pyarrow null-type → loader cast text; datagen nên fix thành string |
| command_source | string | |
| source | string | |

⚠ **GAP P0**: thiếu `scenario_id`/`world_run_id` (zone_state có rồi).
Loader hiện inject qua CLI `--world-run/--scenario`; task cho Opus: thêm 2 cột
này vào `datagen/pipeline.py::build device_state` cho đối xứng.

## zone_sensor_edge_15m.parquet → bảng `zone_sensor_15m`

timestamp, zone_id, temperature_c, humidity_pct, co2_ppm, total_power_kw,
source, scenario_id, world_run_id. Có nhiễu + dropout (NULL) — đây là "cái
sensor thấy", khác zone_state (ground truth). Forecaster train trên sensor,
M&V tính trên zone_state.

## schedules_15m.parquet (input cho E+, không nạp DB ở P0)

timestamp, zone_id, occupancy_count, occupancy_frac, occupancy_state,
lighting_frac, plug_frac, cooling_setpoint_c.
Đây là **input contract cho action_to_idf**: agent variant = sửa các cột này
(setpoint/lighting_frac/occupancy giữ nguyên) rồi rebuild IDF schedule.

## Quy tắc loader (scripts/load_parquet_to_db.py)

1. `SET timezone = 'Asia/Ho_Chi_Minh'` trong session trước khi COPY
   (naive → timestamptz đúng giờ VN).
2. Entities nạp trước từ `Dataset/BIM/extracted/office_concrete/zone_equipment_map.json`
   (+ `tools/idf/out/archetype_zone_map.json` để gắn `zones.archetype`).
3. Time-series COPY theo chunk (500k dòng), không FK, idempotent bằng
   `DELETE WHERE world_run_id = $RUN` trước khi nạp lại run đó.
4. `fault_state` null-type → cast `None` → SQL NULL.
5. Mọi run mới (agent variant) phải INSERT `world_runs` trước khi COPY telemetry.
