"""Prediction Agent: schedule-aware short-horizon forecast (P0, no ML model).

Forecasts zone load/temperature, comfort risk and building peak risk for the
next 15/30/60 minutes by combining the latest telemetry with the IDF work
schedule shape. Returns confidence + a feature explanation. Never proposes
actions (that is the Control Agent's job).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..state import GreenFlowState

TZ = timezone(timedelta(hours=7))
ROOT = Path(__file__).resolve().parents[4]
SEED_FILE = ROOT / "db" / "seed" / "normalized_building.json"

# Demo contracted-demand reference; shared with the Policy Engine.
CAPACITY_KW = 38.0


def peak_risk_from_utilization(utilization: float) -> float:
    """Ramp: 0 below 45% of contracted demand, 1.0 at ~90%."""
    return round(min(1.0, max(0.0, (utilization - 0.45) * 2.2)), 2)


def _day_ahead_demand(building_id: str) -> dict:
    """Day-ahead (24h) building HVAC demand via LightGBM surrogate + learned
    occupancy profile -> anticipates the afternoon peak so the Control Agent can
    pre-cool in the morning. Best-effort: needs the `ml` extra + a trained model;
    returns {} otherwise so the schedule-aware P0 forecast still works."""
    try:
        from ...db import db_conn
        from ...ml.demand_forecast import forecast_building
    except Exception:
        return {}
    try:
        with db_conn() as conn:
            demand = forecast_building(conn, building_id, datetime.now(TZ), horizon_h=24)
        if demand.get("error"):
            return {}
        peak_kw = demand.get("peak_hvac_kw", 0.0)
        demand["peak_utilization"] = round(peak_kw / CAPACITY_KW, 2) if CAPACITY_KW else 0.0
        demand["peak_level"] = ("high" if peak_kw > 0.85 * CAPACITY_KW else
                                "watch" if peak_kw > 0.6 * CAPACITY_KW else "normal")
        return demand
    except Exception:
        return {}


def run(state: GreenFlowState) -> dict:
    horizon = state.get("forecast_horizon_minutes", 60)
    zones = state.get("zones", [])
    zone_state = state.get("latest_zone_state", {})
    normalized = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    schedules = normalized["schedules"]
    sched_by_zone = {z["entity_key"]: z for z in normalized["zones"]}

    now = datetime.now(TZ)
    hour_now = now.hour + now.minute / 60.0
    hour_next = (hour_now + horizon / 60.0) % 24
    is_weekend = now.weekday() >= 5

    zone_load_forecast: dict[str, dict] = {}
    zone_temp_forecast: dict[str, dict] = {}
    comfort_risk: dict[str, float] = {}
    total_now = total_next = 0.0
    conf_inputs: list[float] = []

    for z in zones:
        key = z["entity_key"]
        st = zone_state.get(key)
        if not st:
            continue
        meta = sched_by_zone.get(key, {})
        occ_sched = schedules.get(meta.get("occupancy_schedule", ""),
                                  {"weekday": [0.5] * 24, "weekend": [0.05] * 24})
        sched = occ_sched["weekend" if is_weekend else "weekday"]
        ratio_now = max(sched[int(hour_now) % 24], 0.02)
        ratio_next = max(sched[int(hour_next) % 24], 0.02)
        scale = ratio_next / ratio_now

        load_now = st.get("total_power_kw") or 0.0
        load_next = round(load_now * (0.5 + 0.5 * scale), 2)  # damped persistence
        temp_now = st.get("temperature_c") or 25.0
        # afternoon ramp adds ~0.3C/h when occupied and pre-peak
        temp_drift = 0.3 * (horizon / 60.0) if 11 <= hour_now < 15 else 0.0
        temp_next = round(temp_now + temp_drift, 1)

        risk = 0.0
        if temp_next > 26.5:
            risk = min(1.0, 0.5 + (temp_next - 26.5) * 0.25)
        elif temp_next > 25.8:
            risk = 0.25 + (temp_next - 25.8) * 0.3
        if (st.get("occupancy_count") or 0) == 0:
            risk *= 0.3
        comfort_risk[key] = round(risk, 2)

        zone_load_forecast[key] = {"now_kw": load_now, "forecast_kw": load_next,
                                   "schedule_ratio": round(scale, 2)}
        zone_temp_forecast[key] = {"now_c": temp_now, "forecast_c": temp_next}
        total_now += load_now
        total_next += load_next
        conf_inputs.append(st.get("occupancy_confidence") or 0.8)

    # Peak risk: forecast building load vs contracted demand, ramped above 45%
    in_peak_window = 13 <= hour_next < 16 or 9.5 <= hour_next < 11.5
    utilization = (total_next / CAPACITY_KW) * (1.3 if in_peak_window else 1.0)
    peak_risk_value = peak_risk_from_utilization(utilization)

    confidence = round(min(0.92, (sum(conf_inputs) / len(conf_inputs) if conf_inputs else 0.7)
                           * (0.95 if not is_weekend else 0.85)), 2)

    high_risk_zones = [k for k, v in comfort_risk.items() if v >= 0.5]
    explanation = {
        "model": "schedule_aware_persistence_v0",
        "horizon_minutes": horizon,
        "top_features": [
            {"feature": "occupancy_schedule_ratio", "weight": 0.45},
            {"feature": "current_load_persistence", "weight": 0.35},
            {"feature": "afternoon_temperature_ramp", "weight": 0.20},
        ],
        "notes": "P0 deterministic forecast; LightGBM surrogate planned for P1.",
    }

    demand_forecast = _day_ahead_demand(state["building_id"])

    return {
        "forecast_result": {
            "zone_load_forecast": zone_load_forecast,
            "zone_temperature_forecast": zone_temp_forecast,
            "building_load_now_kw": round(total_now, 2),
            "building_load_forecast_kw": round(total_next, 2),
            "high_comfort_risk_zones": high_risk_zones,
        },
        "comfort_risk": comfort_risk,
        "peak_risk": {"value": peak_risk_value,
                      "level": "high" if peak_risk_value > 0.7 else
                               ("watch" if peak_risk_value > 0.4 else "normal"),
                      "in_peak_window": in_peak_window},
        "demand_forecast": demand_forecast,
        "forecast_confidence": confidence,
        "prediction_explanation": explanation,
    }
