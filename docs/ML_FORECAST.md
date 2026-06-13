# ML forecast — surrogate vào repo (inference)

Phần ML từ workspace `tools/` đã đưa vào repo dưới `backend/greenflow/ml/`. Repo
**chỉ chạy inference** (ship model đã train); pipeline TRAIN (EnergyPlus DoE) sống
ở `tools/` (offline, cần E+) — xem `tools/DOE_AND_TRAINING.md`.

## Module (backend/greenflow/ml/)

| File | Vai trò |
|---|---|
| `models/surrogate_{cooling,temp}.txt` + `surrogate_meta.json` | Model LightGBM đã train (E+ DoE setpoint×occupancy×weather, R² 0.97/0.94) + residual-sigma cho confidence. |
| `forecast_service.py` | **Tự chứa** (không cần datagen/E+). Load model, `what_if(setpoint_delta)`, predict, confidence, đổi nhiệt→điện qua COP part-load. Lịch/COP/tariff inline. |
| `scoring.py` | action → KPI dict (saving_kwh, cost, peak, comfort_delta, rebound) **khớp `agent/regret.py`**. `estimate_action()` cho quick_estimate. |
| `occupancy_profile.py` | Hồ sơ occupancy học từ `telemetry_zone_15m` (DB) theo zone×daytype×slot + override sự kiện. KHÔNG phải ML forecaster (occupancy tất định). |
| `demand_forecast.py` | Hồ sơ + thời tiết → surrogate → điện/peak tòa nhà N giờ → cảnh báo + trigger pre-cool. |

## Đã wire vào agent

`agent/tools/simulation_tool.quick_estimate` giờ dùng **surrogate** (`ml.scoring.
estimate_action`) để chấm candidate action, **fallback rule** cũ nếu thiếu model/
lightgbm. → agent xếp hạng action bằng model thật thay vì công thức tuyến tính.

## Phân vai (trung thực)

- **Surrogate** = chấm nhanh what-if (đổi setpoint/occupancy), interpolate trong
  dải DoE đã train (out-of-grid validate R²=0.978 ở spine). Structural = không
  quán tính → ước tính trạng thái ổn định TRONG cửa sổ action.
- **EnergyPlus** (offline, `tools/`) = validate plan cuối + lượng pre-cool giảm peak
  (phần tích khối nhiệt surrogate không có).
- **demand_forecast** = TRIGGER nhìn trước (baseline), không định lượng lợi ích pre-cool.

## Cài & dùng

```bash
pip install -e ".[ml]"     # lightgbm + numpy + pandas (thiếu -> quick_estimate fallback rule)
```
```python
from greenflow.ml.forecast_service import ForecastService
svc = ForecastService.load_default()   # None nếu chưa cài/thiếu model
wi = svc.what_if("open_office", 190.0, start, 120, setpoint_base=24, setpoint_delta=1.5)
```

## Đã kiểm chứng (repo)

eco +1.5°C → tiết kiệm điện dương, conf 0.94; setpoint 23→27°C cooling giảm dần;
pre-cool saving âm (tốn trước, đúng); scoring ra KPI khớp regret; occupancy profile
học từ DB (localize giờ VN); demand_forecast ra peak + cảnh báo pre-cool heatwave.
5 test ml pass + 37 test cũ pass.
