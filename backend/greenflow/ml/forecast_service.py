"""ForecastService — surrogate LightGBM (train từ EnergyPlus DoE) cho agent gọi.

TỰ CHỨA: không phụ thuộc tools/datagen hay EnergyPlus. Chỉ cần model files trong
ml/models/ (surrogate_cooling.txt, surrogate_temp.txt, surrogate_meta.json) +
hằng số lịch/COP inline dưới đây. Pipeline TRAIN model (DoE + E+) sống ở
workspace `tools/` (offline); repo chỉ ship model + inference. Xem docs/ML_FORECAST.md.

Vai trò: surrogate CHẤM nhanh what-if (đổi setpoint/occupancy) cho agent; E+ (offline)
validate plan cuối. Structural model = không quán tính → ước tính trạng thái ổn định
trong cửa sổ action; rebound/recool sau action do E+ xác nhận.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np

MODEL_DIR = Path(__file__).resolve().parent / "models"
STEP_MIN = 15
STEP_H = STEP_MIN / 60.0
ARCHES = ["open_office", "office", "meeting", "amenity", "circulation"]
FEATURES = ["hour_sin", "hour_cos", "dow", "is_weekend", "occupancy_intensity",
            "lights_frac", "setpoint_c", "outdoor_temp", "outdoor_rh",
            "outdoor_ghi", "area_m2", "category"]

# room_type (DB zones) -> archetype của model
ROOM_TYPE_TO_ARCHE = {
    "open_office": "open_office", "office": "office", "meeting_room": "meeting",
    "meeting": "meeting", "amenity": "amenity", "hallway": "circulation",
    "circulation": "circulation", "lobby": "circulation",
}

# Lịch giờ-trong-ngày (mirror tools/datagen/config — để dựng lại feature như lúc train)
OCC_PROFILE = {
    "open_office": [0, 0, 0, 0, 0, 0, .05, .3, .7, .9, .92, .9, .55, .6, .9, .92, .85, .6, .25, .08, .02, 0, 0, 0],
    "office":      [0, 0, 0, 0, 0, 0, .05, .3, .7, .9, .92, .9, .55, .6, .9, .92, .85, .6, .25, .08, .02, 0, 0, 0],
    "meeting":     [0, 0, 0, 0, 0, 0, 0, .1, .3, .5, .6, .4, .2, .5, .6, .5, .4, .2, .05, 0, 0, 0, 0, 0],
    "amenity":     [0, 0, 0, 0, 0, 0, .05, .15, .2, .2, .25, .5, .7, .5, .25, .2, .25, .4, .2, .1, .05, 0, 0, 0],
    "circulation": [.02, .02, .02, .02, .02, .03, .1, .3, .4, .35, .3, .4, .5, .4, .3, .35, .4, .45, .3, .15, .08, .05, .03, .02],
}
LIGHTS_PROFILE = [0, 0, 0, 0, 0, 0, .1, .5, .9, 1, 1, 1, .8, .9, 1, 1, .9, .6, .2, .1, 0, 0, 0, 0]
OTHER_DAY_FRAC = 0.05
COMFORT_MAX_C = {"open_office": 26.0, "office": 26.0, "meeting": 26.0,
                 "amenity": 27.0, "circulation": 29.0}

# COP part-load + tariff (mirror tools/datagen/config) để đổi nhiệt -> điện -> tiền
COP_RATED, COP_TEMP_REF_C, COP_TEMP_SLOPE = 3.5, 30.0, 0.025
COP_PLR_MIN_FACTOR, COP_PLR_KNEE, COP_DESIGN_W_M2 = 0.75, 0.5, 120.0
TARIFF_PEAK, TARIFF_OFFPEAK = 3200.0, 1800.0
PEAK_HOURS = set(range(9, 12)) | set(range(13, 17))
CO2_KG_PER_KWH = 0.62


def archetype_of(room_type: str | None) -> str:
    return ROOM_TYPE_TO_ARCHE.get((room_type or "").lower(), "office")


def tariff_vnd(hour: int) -> float:
    return TARIFF_PEAK if hour in PEAK_HOURS else TARIFF_OFFPEAK


def default_weather(index) -> dict:
    """Fallback thời tiết Hà Nội khi chưa có bảng weather: temp sin, RH/GHI hợp lý.
    Đủ cho what-if (baseline vs action cùng weather -> delta robust)."""
    h = np.array([t.hour + t.minute / 60 for t in index])
    return {
        "temp": 30.0 + 4.5 * np.sin(2 * np.pi * (h - 9.5) / 24),
        "rh": np.clip(70 - 10 * np.sin(2 * np.pi * (h - 9.5) / 24), 45, 95),
        "ghi": np.clip(900 * np.sin(np.pi * (h - 6) / 12.5), 0, None),
    }


def effective_cop(thermal_kw, outdoor_temp_c, rated_kw):
    f_temp = np.clip(1 - COP_TEMP_SLOPE * (outdoor_temp_c - COP_TEMP_REF_C), 0.5, 1.3)
    plr = np.clip(thermal_kw / np.maximum(rated_kw, 1e-6), 0.0, 1.0)
    f_plr = COP_PLR_MIN_FACTOR + (1 - COP_PLR_MIN_FACTOR) * np.clip(plr / COP_PLR_KNEE, 0, 1)
    return COP_RATED * f_temp * f_plr


def _schedule(index, archetype):
    hours = np.array([t.hour for t in index])
    weekday = np.array([t.weekday() < 5 for t in index])
    occ_p = np.array(OCC_PROFILE.get(archetype, OCC_PROFILE["office"]))
    occ = np.where(weekday, occ_p[hours], OTHER_DAY_FRAC)
    light = np.where(weekday, np.array(LIGHTS_PROFILE)[hours], OTHER_DAY_FRAC)
    return occ, light


@dataclass
class WhatIf:
    timestamps: list
    baseline_elec_kwh: np.ndarray
    action_elec_kwh: np.ndarray
    baseline_temp_c: np.ndarray
    action_temp_c: np.ndarray
    confidence: float


class ForecastService:
    def __init__(self, cooling, temp, meta):
        self.cooling, self.temp, self.meta = cooling, temp, meta
        self._sigma = meta["targets"]["y_cooling_kwh"]["residual_sigma_by_cat_hour"]

    @classmethod
    @lru_cache(maxsize=1)
    def load_default(cls) -> "ForecastService | None":
        """Load model 1 lần; None nếu thiếu file/lightgbm (caller fallback heuristic)."""
        try:
            import lightgbm as lgb
            meta = json.loads((MODEL_DIR / "surrogate_meta.json").read_text())
            return cls(lgb.Booster(model_file=str(MODEL_DIR / "surrogate_cooling.txt")),
                       lgb.Booster(model_file=str(MODEL_DIR / "surrogate_temp.txt")), meta)
        except Exception:  # noqa: BLE001 — thiếu model/lib -> caller dùng heuristic
            return None

    def _features(self, archetype, area_m2, index, setpoint, occ_intensity, weather):
        occ_base, light = _schedule(index, archetype)
        if occ_intensity is None:
            occ_intensity = occ_base
        w = weather or default_weather(index)
        hours = np.array([t.hour for t in index])
        import pandas as pd
        return pd.DataFrame({
            "hour_sin": np.sin(2 * np.pi * hours / 24), "hour_cos": np.cos(2 * np.pi * hours / 24),
            "dow": [t.weekday() for t in index],
            "is_weekend": [1 if t.weekday() >= 5 else 0 for t in index],
            "occupancy_intensity": occ_intensity, "lights_frac": light,
            "setpoint_c": setpoint, "outdoor_temp": w["temp"], "outdoor_rh": w["rh"],
            "outdoor_ghi": w["ghi"], "area_m2": float(area_m2),
            "category": ARCHES.index(archetype) if archetype in ARCHES else 1,
        })[FEATURES]

    def predict(self, archetype, area_m2, index, setpoint, occ_intensity=None, weather=None):
        X = self._features(archetype, area_m2, index, setpoint, occ_intensity, weather)
        return np.clip(self.cooling.predict(X), 0, None), self.temp.predict(X)

    def _to_elec(self, cooling_kwh, area_m2, index, weather):
        w = weather or default_weather(index)
        thermal_kw = cooling_kwh / STEP_H
        rated = float(area_m2) * COP_DESIGN_W_M2 / 1000.0
        return thermal_kw / effective_cop(thermal_kw, w["temp"], rated) * STEP_H

    def _confidence(self, archetype, index, yhat):
        ci = ARCHES.index(archetype) if archetype in ARCHES else 1
        sig = np.array([self._sigma.get(f"{ci}_{t.hour}", 0.1) for t in index])
        return float(np.clip(1 - sig.mean() / (np.abs(yhat).mean() + 1e-3), 0, 1))

    def what_if(self, archetype, area_m2, start: datetime, horizon_min, setpoint_base,
                setpoint_delta, occ_intensity=None, weather=None) -> WhatIf:
        n = max(1, horizon_min // STEP_MIN)
        index = [start + timedelta(minutes=STEP_MIN * i) for i in range(n)]
        bc, bt = self.predict(archetype, area_m2, index, setpoint_base, occ_intensity, weather)
        ac, at = self.predict(archetype, area_m2, index, setpoint_base + setpoint_delta,
                              occ_intensity, weather)
        return WhatIf(index, self._to_elec(bc, area_m2, index, weather),
                      self._to_elec(ac, area_m2, index, weather), bt, at,
                      min(self._confidence(archetype, index, bc),
                          self._confidence(archetype, index, ac)))
