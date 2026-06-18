"""Dự báo điện/peak tòa nhà N giờ tới -> đón đầu pre-cool.

Hồ sơ occupancy (tất định) + thời tiết sắp tới -> surrogate -> điện HVAC từng
zone -> tổng tòa nhà. Cảnh báo peak + phát hiện chiều nóng+đông -> đề xuất pre-cool.

Trung thực: đây là TRIGGER nhìn-trước (baseline demand). Lượng pre-cool giảm peak
do EnergyPlus validate (surrogate structural không có quán tính khối nhiệt).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from ..db import fetch_all
from .forecast_service import (STEP_MIN, ForecastService, archetype_of,
                               default_weather)
from .occupancy_profile import OccupancyProfile

WORK_START, WORK_END = 7, 19
PEAK_WINDOW = range(13, 17)
HEATWAVE_C = 35.0


def _setpoint(index, precool: bool) -> np.ndarray:
    sp = np.array([24.0 if WORK_START <= t.hour < WORK_END else 28.0 for t in index])
    if precool:
        sp[[5 <= t.hour < 8 for t in index]] = 22.0
    return sp


def forecast_building(conn, building_id, issued_ts: datetime, horizon_h: int = 24,
                      weather_shift: float = 0.0) -> dict:
    svc = ForecastService.load_default()
    if svc is None:
        return {"error": "surrogate model not available"}
    profile = OccupancyProfile.learn(conn, building_id)
    zones = fetch_all(conn, "SELECT entity_key, room_type, area_m2 FROM zones "
                      "WHERE building_id = :b", b=building_id)
    n = horizon_h * 4
    index = [issued_ts + timedelta(minutes=STEP_MIN * i) for i in range(n)]
    w = default_weather(index)
    w = {"temp": w["temp"] + weather_shift, "rh": w["rh"], "ghi": w["ghi"]}
    setpoint = _setpoint(index, precool=False)

    hvac_kw = np.zeros(n)
    for z in zones:
        occ = [profile.expected(z["entity_key"], t)["frac"] for t in index]
        cooling, _ = svc.predict(archetype_of(z["room_type"]), z["area_m2"] or 50.0,
                                 index, setpoint, occ_intensity=occ, weather=w)
        hvac_kw += svc._to_elec(cooling, z["area_m2"] or 50.0, index, w) / (STEP_MIN / 60)

    peak_i = int(np.argmax(hvac_kw))
    peak_kw, peak_ts = float(hvac_kw[peak_i]), index[peak_i]
    aft = np.array([t.hour in PEAK_WINDOW for t in index])
    alerts = []
    if aft.any() and w["temp"][aft].max() >= HEATWAVE_C:
        hot = index[int(np.argmax(np.where(aft, w["temp"], -99)))]
        alerts.append(f"Pre-cool đề xuất: chiều {hot:%d/%m} nóng {w['temp'][aft].max():.0f}°C "
                      f"-> pre-cool sáng {hot.replace(hour=6, minute=0):%H:%M} (E+ validate mức giảm)")

    # Structured pre-cool recommendation (downstream control reads this, không parse string).
    # Đón đầu: peak rơi vào cửa sổ chiều -> charge khối nhiệt sáng sớm (điện rẻ, ngoài trời mát).
    recommend_precool = bool(alerts) or (peak_ts.hour in PEAK_WINDOW)
    precool_window = {"start_hour": 6, "end_hour": 8} if recommend_precool else None
    return {
        "issued_at": str(issued_ts), "horizon_hours": horizon_h,
        "peak_hvac_kw": round(peak_kw, 1), "peak_at": str(peak_ts),
        "peak_hour": peak_ts.hour,
        "recommend_precool": recommend_precool,
        "precool_window": precool_window,
        "series": [{"ts": str(t), "hvac_kw": round(float(k), 1)}
                   for t, k in zip(index, hvac_kw)],
        "alerts": alerts,
    }
