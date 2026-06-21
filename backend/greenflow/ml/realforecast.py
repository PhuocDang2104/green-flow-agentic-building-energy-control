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
