# Dự báo demand day-ahead → Pre-cool (đón đầu peak)

> Nối module `demand_forecast` + `occupancy_profile` (trước đây mồ côi) vào agent
> và expose ra API cho dashboard. Mục tiêu: **nhìn trước peak buổi chiều ngay từ
> sáng** để agent đề xuất pre-cool (charge khối nhiệt) chủ động, thay vì chỉ phản
> ứng theo forecast 60 phút.

---

## 1. Vấn đề trước khi sửa

- `ml/demand_forecast.py` và `ml/occupancy_profile.py` đã build nhưng **không được
  import ở đâu** ngoài chính nó → giá trị cốt lõi "đón đầu pre-cool" chưa chạy thật.
- Node `prediction` chỉ dự báo **ngắn hạn 60 phút** (persistence + schedule shape).
  Nó không thể biết "chiều nay 15:00 sẽ nóng + đông" để pre-cool từ **sáng 06:00**.
- Node `control` chỉ bật `pre_cooling` khi `peak_risk` ngắn hạn đã ở mức watch/high
  — tức là khi peak gần như sắp xảy ra, đã trễ để charge khối nhiệt.

## 2. Cơ chế (data flow)

```
building_semantic ──► prediction ──► control ──► simulation ──► policy ──► execution
                          │              │
                          │ (mới)        │ đọc state["demand_forecast"]
                          ▼              ▼
                   _day_ahead_demand()   nếu recommend_precool → action "pre_cooling"
                          │                  start=06:00, reason có peak_kw + giờ peak
                          ▼
        ml/demand_forecast.forecast_building(conn, building_id, now, 24h)
                          │
        ┌─────────────────┴─────────────────┐
        ▼                                     ▼
 OccupancyProfile.learn(conn)         ForecastService (LightGBM surrogate)
 (median telemetry theo               cooling/zone theo setpoint × occupancy ×
  zone × daytype × slot 15')          thời tiết → điện HVAC → tổng tòa nhà
```

### Bước 1 — `prediction` gọi dự báo day-ahead (best-effort)
`backend/greenflow/agent/nodes/prediction.py` thêm `_day_ahead_demand(building_id)`:

- Mở `db_conn()`, gọi `forecast_building(conn, building_id, now, horizon_h=24)`.
- Tính thêm `peak_utilization = peak_kw / CAPACITY_KW` và `peak_level`
  (high > 85% capacity, watch > 60%, else normal).
- **An toàn:** import `ml` đặt trong `try/except` (giống `simulation_tool`). Nếu
  thiếu extra `ml`, thiếu model, hoặc DB lỗi → trả `{}` và forecast ngắn hạn P0 vẫn chạy.
- Kết quả ghi vào `state["demand_forecast"]` (key mới trong `GreenFlowState`).

### Bước 2 — `forecast_building` sinh khuyến nghị pre-cool có cấu trúc
`backend/greenflow/ml/demand_forecast.py` trả thêm 3 field để **downstream không
phải parse chuỗi**:

| Field | Ý nghĩa |
|---|---|
| `peak_hour` | giờ rơi peak (vd 15) |
| `recommend_precool` | `True` nếu có cảnh báo nắng nóng **hoặc** peak rơi vào cửa sổ chiều 13–17h |
| `precool_window` | `{start_hour: 6, end_hour: 8}` — charge khối nhiệt sáng sớm (điện rẻ, ngoài trời mát) |

Cộng các field cũ: `peak_hvac_kw`, `peak_at`, `series` (96 điểm/24h), `alerts`.

### Bước 3 — `control` ra quyết định pre-cool theo day-ahead
`backend/greenflow/agent/nodes/control.py`:

- `day_ahead = demand.peak_level ∈ {watch, high}  OR  demand.recommend_precool`
- Trigger khối peak khi: `peak_risk` ngắn hạn cao **hoặc** `peak_mode` (nút)
  **hoặc** `day_ahead` (← mới, đón đầu).
- Nếu `recommend_precool`, dùng `precool_window` (06:00–08:00) thay vì cửa sổ mặc
  định 11–13h, và **reason có số liệu thật**:
  > "Day-ahead forecast peaks 14.0 kW around 15:00; pre-cool early (06:00) to
  > charge thermal mass while power is cheaper and outdoor air is cooler"
- Action vẫn đi qua `quick_estimate` (surrogate) + `policy` gate + `simulation`
  như mọi action khác → **không bỏ qua audit**.

## 3. API cho dashboard (Tab 2)

`backend/greenflow/api/routers/forecast.py` (mới):

| Endpoint | Trả về |
|---|---|
| `GET /api/forecast/demand?building_id&horizon_h&weather_shift` | đường demand HVAC day-ahead, `peak_hvac_kw`, `peak_at`, `recommend_precool`, `precool_window`, `alerts`. `weather_shift` (°C) là núm what-if nắng nóng. |
| `GET /api/forecast/occupancy?building_id&horizon_h&step_min` | occupancy kỳ vọng theo zone (frac/count/confidence) + đường tổng tòa nhà, từ hồ sơ học được. |

- Thiếu extra `ml` → **503** (không đoán bừa). Thiếu model → 503 với thông báo rõ.
- `> ⚠️ TRẠNG THÁI: file đã tạo nhưng dòng đăng ký trong `api/main.py` CHƯA được
  thêm` — cần thêm `forecast` vào import + vòng `include_router` thì endpoint mới
  sống. (Edit này đang chờ.)

## 4. Tính trung thực (đọc kỹ)

- Surrogate là **structural model** (cooling = f(setpoint, occupancy, thời tiết)),
  **không có** lag/quán tính → dùng được cho what-if (đổi setpoint thì cooling đổi).
  Nó cho biết **baseline demand + khi nào peak**, đóng vai TRIGGER nhìn trước.
- **Mức giảm peak thực tế của pre-cool** (nhờ khối nhiệt bê tông) do EnergyPlus
  validate, không phải surrogate — đúng như docstring `demand_forecast` ghi.
- `occupancy_profile` **không phải** ML forecaster: nó là bảng trung vị telemetry
  theo zone × loại ngày × slot 15'. Real-time occupancy = YOLO (riêng). Vì người
  ra/vào văn phòng lặp lại nên hồ sơ tất định là đủ.
- Thời tiết day-ahead hiện dùng đường diurnal tổng hợp (`default_weather`) +
  `weather_shift`; thay bằng forecast khí tượng thật là cải tiến tương lai.

## 5. File đã đổi

| File | Thay đổi |
|---|---|
| `backend/greenflow/ml/demand_forecast.py` | + `peak_hour`, `recommend_precool`, `precool_window` |
| `backend/greenflow/agent/state.py` | + key `demand_forecast` |
| `backend/greenflow/agent/nodes/prediction.py` | + `_day_ahead_demand()` → `state["demand_forecast"]` |
| `backend/greenflow/agent/nodes/control.py` | pre-cool đọc day-ahead forecast |
| `backend/greenflow/api/routers/forecast.py` | **mới** — 2 endpoint forecast |
| `backend/greenflow/api/main.py` | đăng ký router *(đang chờ)* |

## 6. Kiểm thử

- `pytest backend/tests/test_agent_plans.py test_ml_forecast.py` → **11 passed**.
- Smoke test `forecast_building` với DB stub + surrogate thật: peak 14.0 kW @
  15:00, `recommend_precool=True`, `precool_window={6,8}`, alert nắng nóng 38°C,
  `series` đủ 96 điểm. Path tính toán day-ahead → control pre-cool chạy đúng.
- Fallback đã kiểm: thiếu DB/model → `_day_ahead_demand` trả `{}`, agent vẫn chạy.
</content>
