"""Surrogate THẬT (LightGBM, train trên 1 năm EnergyPlus + Open-Meteo 2025).

Khác surrogate cũ (DoE tổng hợp, dự báo nhiệt->COP): model này học từ dữ liệu
thật, dự báo ĐIỆN trực tiếp, feature toàn số (inference tái lập dễ). Test metrics
(held-out split) trong surrogate_real_meta.json: zone R²≈0.92, building R²≈0.87.

Dùng cho what-if setpoint ở action scoring. What-if là DELTA (base vs action,
cùng weather/zone) nên sai số tuyệt đối triệt tiêu -> ước lượng tiết kiệm robust.
Thiếu model/lightgbm -> trả None (caller fallback surrogate cũ / rule).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np

MODEL_DIR = Path(__file__).resolve().parent / "models"
REF_DAY = datetime(2025, 7, 15)  # ngày hè điển hình cho what-if
STEP_MIN = 30


@lru_cache(maxsize=1)
def _load_zone():
    try:
        import lightgbm as lgb
        meta = json.loads((MODEL_DIR / "surrogate_real_meta.json").read_text())
        feats = meta["models"]["zone"]["features"]
        return (lgb.Booster(model_file=str(MODEL_DIR / "surrogate_real_zone.txt")), feats)
    except Exception:  # noqa: BLE001 — thiếu model/lib
        return None


def test_metrics() -> dict | None:
    """Metrics test giữ riêng (cho pitch / Impact tab)."""
    try:
        return json.loads((MODEL_DIR / "surrogate_real_meta.json").read_text())["models"]
    except Exception:  # noqa: BLE001
        return None


def _weather(index, shift: float = 0.0) -> dict:
    h = np.array([t.hour + t.minute / 60 for t in index])
    return {
        "outdoor_temp_c": 30.0 + 4.5 * np.sin(2 * np.pi * (h - 9.5) / 24) + shift,
        "outdoor_rh_pct": np.clip(70 - 10 * np.sin(2 * np.pi * (h - 9.5) / 24), 45, 95),
        "global_horizontal_radiation_wh_m2": np.clip(900 * np.sin(np.pi * (h - 6) / 12.5), 0, None),
        "wind_speed_m_s": np.full(len(index), 2.0),
        "cloud_cover_pct": np.full(len(index), 40.0),
    }


def _frame(index, area, volume, ceiling, setpoint, w, feats):
    import pandas as pd
    hours = np.array([t.hour for t in index])
    dow = np.array([t.weekday() for t in index])
    mon = np.array([t.month for t in index])
    full = {
        "outdoor_temp_c": w["outdoor_temp_c"], "outdoor_rh_pct": w["outdoor_rh_pct"],
        "global_horizontal_radiation_wh_m2": w["global_horizontal_radiation_wh_m2"],
        "wind_speed_m_s": w["wind_speed_m_s"], "cloud_cover_pct": w["cloud_cover_pct"],
        "hour_sin": np.sin(2 * np.pi * hours / 24), "hour_cos": np.cos(2 * np.pi * hours / 24),
        "dayofweek_sin": np.sin(2 * np.pi * dow / 7), "dayofweek_cos": np.cos(2 * np.pi * dow / 7),
        "month_sin": np.sin(2 * np.pi * mon / 12), "month_cos": np.cos(2 * np.pi * mon / 12),
        "office_hours_flag": np.array([1 if (7 <= t.hour < 19 and t.weekday() < 5) else 0
                                       for t in index]),
        "cooling_setpoint_c": np.asarray(setpoint, dtype=float),
        "area_m2": float(area), "volume_m3": float(volume), "ceiling_height_m": float(ceiling),
    }
    return pd.DataFrame({k: full[k] for k in feats})


def what_if_setpoint(area_m2: float, setpoint_base: float, setpoint_delta: float,
                     start_hour: float, end_hour: float, *, ceiling: float = 3.0,
                     weather_shift: float = 0.0) -> dict | None:
    """Điện tiết kiệm (kWh) + giảm đỉnh (kW) khi dời setpoint, bằng surrogate thật."""
    m = _load_zone()
    if m is None:
        return None
    booster, feats = m
    n = max(1, int(round((end_hour - start_hour) * 60 / STEP_MIN)))
    index = [REF_DAY + timedelta(hours=start_hour, minutes=STEP_MIN * i) for i in range(n)]
    w = _weather(index, weather_shift)
    vol = area_m2 * ceiling
    base = np.clip(booster.predict(_frame(index, area_m2, vol, ceiling,
                                          np.full(n, setpoint_base), w, feats)), 0, None)
    act = np.clip(booster.predict(_frame(index, area_m2, vol, ceiling,
                                         np.full(n, setpoint_base + setpoint_delta), w, feats)), 0, None)
    return {"saving_kwh": float((base - act).sum()) * STEP_MIN / 60.0,
            "peak_reduction_kw": float(base.max() - act.max()), "confidence": 0.85}


@lru_cache(maxsize=1)
def _load_hvac():
    try:
        import lightgbm as lgb
        meta = json.loads((MODEL_DIR / "surrogate_real_meta.json").read_text())
        feats = meta["models"]["hvac"]["features"]
        return (lgb.Booster(model_file=str(MODEL_DIR / "surrogate_real_hvac.txt")), feats)
    except Exception:  # noqa: BLE001 — thiếu model/lib
        return None


def _scalar_weather(hour: float, outdoor_temp_c=None) -> dict:
    import math
    t = 30.0 + 4.5 * math.sin(2 * math.pi * (hour - 9.5) / 24)
    return {
        "outdoor_temp_c": float(outdoor_temp_c) if outdoor_temp_c is not None else t,
        "outdoor_rh_pct": max(45.0, min(95.0, 70 - 10 * math.sin(2 * math.pi * (hour - 9.5) / 24))),
        "global_horizontal_radiation_wh_m2": max(0.0, 900 * math.sin(math.pi * (hour - 6) / 12.5)),
        "wind_speed_m_s": 2.0, "cloud_cover_pct": 40.0,
    }


def _row(feats, *, area, volume, ceiling, setpoint, hour, month, is_workday, w):
    import pandas as pd
    dow = 2 if is_workday else 6  # representative weekday / weekend
    full = {
        "outdoor_temp_c": w["outdoor_temp_c"], "outdoor_rh_pct": w["outdoor_rh_pct"],
        "global_horizontal_radiation_wh_m2": w["global_horizontal_radiation_wh_m2"],
        "wind_speed_m_s": w["wind_speed_m_s"], "cloud_cover_pct": w["cloud_cover_pct"],
        "hour_sin": np.sin(2 * np.pi * hour / 24), "hour_cos": np.cos(2 * np.pi * hour / 24),
        "dayofweek_sin": np.sin(2 * np.pi * dow / 7), "dayofweek_cos": np.cos(2 * np.pi * dow / 7),
        "month_sin": np.sin(2 * np.pi * month / 12), "month_cos": np.cos(2 * np.pi * month / 12),
        "office_hours_flag": 1 if (7 <= hour < 19 and is_workday) else 0,
        "cooling_setpoint_c": float(setpoint), "area_m2": float(area),
        "volume_m3": float(volume), "ceiling_height_m": float(ceiling),
    }
    return pd.DataFrame({k: [full[k]] for k in feats})


def predict_zone_state(*, area_m2: float, cooling_setpoint_c: float, hour: int = 14,
                       month: int = 7, is_workday: bool = True, occupied: bool = True,
                       ceiling_height_m: float = 3.0, volume_m3: float | None = None,
                       outdoor_temp_c: float | None = None) -> dict:
    """Predict a zone's operational state (the telemetry fields) for given inputs.

    Real LightGBM surrogates for total + HVAC power; temperature and comfort/peak
    risk derived. EVERY field has a heuristic fallback so the system keeps running
    even if a model, the lib, or an input is missing — this is the operability
    contract for the parameter / data-input setup flow.
    """
    vol = float(volume_m3) if volume_m3 else area_m2 * ceiling_height_m
    w = _scalar_weather(hour, outdoor_temp_c)
    sources: dict[str, str] = {}

    def _predict(loader, name: str):
        try:
            m = loader()
            if m is None:
                return None
            booster, feats = m
            row = _row(feats, area=area_m2, volume=vol, ceiling=ceiling_height_m,
                       setpoint=cooling_setpoint_c, hour=hour, month=month,
                       is_workday=is_workday, w=w)
            sources[name] = "surrogate"
            return max(0.0, float(booster.predict(row)[0]))
        except Exception:  # noqa: BLE001 — any failure -> heuristic below
            return None

    total = _predict(_load_zone, "total_power_kw")
    hvac = _predict(_load_hvac, "hvac_power_kw")
    if total is None:
        total = 0.03 * area_m2 * (1.0 if occupied else 0.3)
        sources["total_power_kw"] = "heuristic"
    if hvac is None:
        hvac = 0.28 * total
        sources["hvac_power_kw"] = "heuristic"

    # temperature: when the cooling system is actively drawing power the zone holds
    # near setpoint; when HVAC is essentially off it drifts toward the outdoor air.
    # Derived (no real zone-temp target in the training set).
    if hvac > 0.15:
        temp = cooling_setpoint_c + 0.5
    else:
        temp = cooling_setpoint_c + max(0.0, w["outdoor_temp_c"] - cooling_setpoint_c) * 0.5
    sources["temperature_c"] = "derived"

    comfort = ("high" if occupied and temp > 26.5 else
               "watch" if occupied and temp > 25.5 else "normal")
    in_peak = 13 <= hour < 16
    peak = ("high" if in_peak and total > 0.05 * area_m2 else "watch" if in_peak else "normal")
    sources["comfort_risk"] = sources["peak_risk"] = "rule"

    return {
        "total_power_kw": round(total, 3), "hvac_power_kw": round(hvac, 3),
        "temperature_c": round(temp, 2), "comfort_risk": comfort, "peak_risk": peak,
        "sources": sources,
    }
