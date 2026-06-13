"""Chấm tác động action bằng surrogate -> KPI dict (khớp agent/regret.py).

Output keys khớp regrettable_substitution_check: saving_kwh, cost_saving_vnd,
peak_reduction_kw, comfort_violation_delta_min, rebound_kwh (+ co2, confidence).
Dùng để nâng simulation_tool.quick_estimate từ rule thô -> surrogate thật.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np

from .forecast_service import (COMFORT_MAX_C, STEP_MIN, ForecastService,
                               archetype_of, tariff_vnd)

# action_type -> setpoint delta (°C). lighting xử lý riêng (tính trực tiếp).
SETPOINT_DELTA = {"hvac_eco_mode": 1.5, "hvac_setback_light": 1.0, "hvac_setback": 1.0,
                  "pre_cooling": -1.0, "peak_load_reduction": 1.5, "demand_response": 1.5}
LIGHTING_FACTOR = {"lighting_reduction": 0.6, "turn_off_non_critical_lighting": 0.3}
LPD_W_M2 = 11.0  # mật độ đèn (QCVN office)
REF_DAY = datetime(2025, 7, 15)  # ngày hè điển hình (thứ Ba) cho replay clock


def _start(hour: float) -> datetime:
    return REF_DAY.replace(hour=int(hour) % 24, minute=int((hour % 1) * 60))


def score_zone_action(svc: ForecastService, action_type: str, room_type: str,
                      area_m2: float, start_hour: float, end_hour: float,
                      setpoint_base: float = 24.0, occ_intensity=None,
                      weather=None) -> dict:
    """KPI cho 1 action trên 1 zone. Quy ước dấu: dương = tốt (tiết kiệm),
    trừ comfort_violation_delta_min (dương = comfort xấu đi)."""
    arche = archetype_of(room_type)
    horizon = max(STEP_MIN, int((end_hour - start_hour) * 60))
    start = _start(start_hour)
    delta = SETPOINT_DELTA.get(action_type)

    if delta is not None:
        wi = svc.what_if(arche, area_m2, start, horizon, setpoint_base, delta,
                         occ_intensity=occ_intensity, weather=weather)
        save = float((wi.baseline_elec_kwh - wi.action_elec_kwh).sum())
        cost = float(sum((b - a) * tariff_vnd(t.hour) for b, a, t in
                         zip(wi.baseline_elec_kwh, wi.action_elec_kwh, wi.timestamps)))
        peak = float(wi.baseline_elec_kwh.max() - wi.action_elec_kwh.max()) / (STEP_MIN / 60)
        cmax = COMFORT_MAX_C.get(arche, 26.0)
        comfort_delta = float(((wi.action_temp_c > cmax).sum()
                               - (wi.baseline_temp_c > cmax).sum()) * STEP_MIN)
        conf = wi.confidence
    elif action_type in LIGHTING_FACTOR:
        hours = (end_hour - start_hour)
        save = area_m2 * LPD_W_M2 / 1000.0 * (1 - LIGHTING_FACTOR[action_type]) * hours * 0.8
        cost = save * tariff_vnd(int(start_hour))
        peak, comfort_delta, conf = 0.0, 0.0, 0.9
    else:
        save = cost = peak = comfort_delta = 0.0
        conf = 0.5

    return {
        "saving_kwh": round(save, 3), "cost_saving_vnd": round(cost, 0),
        "peak_reduction_kw": round(peak, 3), "comfort_violation_delta_min": round(comfort_delta, 1),
        "co2_avoided_kg": round(save * 0.62, 3), "rebound_kwh": 0.0,  # rebound: E+ validate
        "confidence": round(float(conf), 3), "estimate_method": "surrogate_what_if",
    }


def estimate_action(action, zones: list[dict], weather=None) -> dict | None:
    """Tương thích simulation_tool.quick_estimate (Action + zones) nhưng dùng
    surrogate. None nếu model chưa sẵn (caller fallback rule)."""
    svc = ForecastService.load_default()
    if svc is None:
        return None
    targets = [z for z in zones if not getattr(action, "target_zone_keys", None)
               or z.get("entity_key") in action.target_zone_keys]
    if not targets:
        targets = zones
    action_type = getattr(action, "action_type", "hvac_eco_mode")
    agg = {"saving_kwh": 0.0, "cost_saving_vnd": 0.0, "peak_reduction_kw": 0.0,
           "comfort_violation_delta_min": 0.0, "co2_avoided_kg": 0.0}
    confs = []
    for z in targets:
        k = score_zone_action(svc, action_type, z.get("room_type"), z.get("area_m2") or 50.0,
                              getattr(action, "start_hour", 13.0),
                              getattr(action, "end_hour", 15.0), weather=weather)
        for key in agg:
            agg[key] += k[key]
        confs.append(k["confidence"])
    return {"expected_saving_kwh": round(agg["saving_kwh"], 2),
            "zones_affected": len(targets),
            "estimate_method": "surrogate_what_if",
            "confidence": round(float(np.mean(confs)) if confs else 0.5, 3),
            "kpi": {k: round(v, 2) for k, v in agg.items()}}
