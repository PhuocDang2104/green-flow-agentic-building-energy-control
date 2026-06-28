"""Prediction Agent: dataset-aligned short-horizon forecast for all 308 zones.

Forecasts zone load/temperature, comfort risk and building peak risk for the
next 15/30/60 minutes by combining the latest telemetry with the IDF work
schedule shape. Returns confidence + a feature explanation. Never proposes
actions (that is the Control Agent's job).
"""

from __future__ import annotations

import math
from datetime import timedelta, timezone

from ...config import get_settings
from ...ml.forecast_service import OCC_PROFILE, archetype_of
from ...replayclock import anchor
from ..state import GreenFlowState

TZ = timezone(timedelta(hours=7))


def contracted_demand_kw() -> float:
    return max(1.0, get_settings().greenflow_contracted_demand_kw)


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
            demand = forecast_building(conn, building_id, anchor(conn, building_id), horizon_h=24)
        if demand.get("error"):
            return {}
        return demand
    except Exception:
        return {}


def _ml_building_forecast(building_id: str, now, horizon_minutes: int) -> dict:
    """Recursive lag forecast through the requested horizon for every zone."""
    try:
        from ...ml import forecast_lag
        if not forecast_lag.available():
            return {}
        from ...db import db_conn, fetch_all
        with db_conn() as conn:
            rows = fetch_all(conn, """
                WITH ranked AS (
                    SELECT z.entity_key AS k, t.timestamp AS ts,
                           t.total_power_kw AS p, t.occupancy_count AS occ,
                           row_number() OVER (
                               PARTITION BY z.entity_key ORDER BY t.timestamp DESC
                           ) AS rn
                    FROM telemetry_zone_15m t JOIN zones z ON z.id = t.zone_id
                    WHERE t.building_id = :b AND t.timestamp <= :now
                )
                SELECT k, ts, p, occ FROM ranked
                WHERE rn <= :history ORDER BY k, ts
            """, b=building_id, now=now, history=forecast_lag.STEPS_PER_DAY)
            wx = fetch_all(conn, "SELECT outdoor_temp_c AS o FROM weather_15m "
                           "WHERE timestamp <= :now ORDER BY timestamp DESC LIMIT 1", now=now)
        if not rows:
            return {}
        otemp = float(wx[0]["o"]) if wx and wx[0]["o"] is not None else 30.0
        step_minutes = 30
        steps = max(1, math.ceil(horizon_minutes / step_minutes))
        future = [now + timedelta(minutes=step_minutes * (step + 1)) for step in range(steps)]
        by_zone: dict[str, list] = {}
        for r in rows:
            by_zone.setdefault(r["k"], []).append((float(r["p"] or 0), float(r["occ"] or 0)))
        zone_forecast: dict[str, float] = {}
        for key, seq in by_zone.items():
            hist = [p for p, _ in seq][-forecast_lag.STEPS_PER_DAY:]
            if len(hist) < 2:
                continue
            rollout = forecast_lag.predict_day_ahead(
                hist, [(seq[-1][1], otemp, timestamp) for timestamp in future]
            )
            if rollout:
                zone_forecast[key] = max(0.0, float(rollout[-1][1]))
        if not zone_forecast:
            return {}
        return {
            "model": "lgbm_lag_total_v2",
            "building_next_kw": round(sum(zone_forecast.values()), 2),
            "zone_forecast_kw": zone_forecast,
            "zone_count": len(zone_forecast),
            "forecast_horizon_minutes": steps * step_minutes,
        }
    except Exception:
        return {}


def run(state: GreenFlowState) -> dict:
    horizon = state.get("forecast_horizon_minutes", 60)
    zones = state.get("zones", [])
    zone_state = state.get("latest_zone_state", {})
    now = anchor()
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
        archetype = archetype_of(z.get("room_type"))
        sched = OCC_PROFILE.get(archetype, OCC_PROFILE["office"])
        if is_weekend:
            sched = [0.05] * 24
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

    # ML lag forecaster for the building headline + peak (best-effort; falls back
    # to the schedule-persistence sum above when the model/history is unavailable).
    ml = _ml_building_forecast(state["building_id"], now, horizon)
    for key, forecast_kw in ml.get("zone_forecast_kw", {}).items():
        if key in zone_load_forecast:
            zone_load_forecast[key]["forecast_kw"] = round(forecast_kw, 2)
    if ml.get("zone_forecast_kw"):
        total_next = sum(item["forecast_kw"] for item in zone_load_forecast.values())
    building_next = ml.get("building_next_kw", round(total_next, 2))
    model_name = ml.get("model", "schedule_aware_persistence_v0")

    # Peak risk: forecast building load vs contracted demand, ramped above 45%
    in_peak_window = 13 <= hour_next < 16 or 9.5 <= hour_next < 11.5
    capacity_kw = contracted_demand_kw()
    utilization = (building_next / capacity_kw) * (1.3 if in_peak_window else 1.0)
    peak_risk_value = peak_risk_from_utilization(utilization)

    confidence = round(min(0.92, (sum(conf_inputs) / len(conf_inputs) if conf_inputs else 0.7)
                           * (0.95 if not is_weekend else 0.85)), 2)

    high_risk_zones = [k for k, v in comfort_risk.items() if v >= 0.5]
    is_ml = bool(ml)
    explanation = {
        "model": model_name,
        "horizon_minutes": horizon,
        "model_horizon_minutes": ml.get("forecast_horizon_minutes", horizon),
        "zone_coverage": ml.get("zone_count", len(zone_load_forecast)),
        "top_features": ([
            {"feature": "current_load (lag0)", "weight": 0.30},
            {"feature": "outdoor_temp", "weight": 0.25},
            {"feature": "load_momentum (delta)", "weight": 0.20},
            {"feature": "same_time_yesterday (lag_day)", "weight": 0.15},
            {"feature": "occupancy", "weight": 0.10},
        ] if is_ml else [
            {"feature": "occupancy_schedule_ratio", "weight": 0.45},
            {"feature": "current_load_persistence", "weight": 0.35},
            {"feature": "afternoon_temperature_ramp", "weight": 0.20},
        ]),
        "notes": ("Dataset-aligned LightGBM recursive lag forecast." if is_ml
                  else "Schedule-aware persistence (ML model unavailable; fallback)."),
    }

    demand_forecast = _day_ahead_demand(state["building_id"])

    return {
        "forecast_result": {
            "zone_load_forecast": zone_load_forecast,
            "zone_temperature_forecast": zone_temp_forecast,
            "building_load_now_kw": round(total_now, 2),
            "building_load_forecast_kw": building_next,
            "high_comfort_risk_zones": high_risk_zones,
        },
        "comfort_risk": comfort_risk,
        "peak_risk": {"value": peak_risk_value,
                      "level": "high" if peak_risk_value > 0.7 else
                               ("watch" if peak_risk_value > 0.4 else "normal"),
                      "in_peak_window": in_peak_window,
                      "contracted_demand_kw": capacity_kw,
                      "forecast_utilization": round(utilization, 3)},
        "demand_forecast": demand_forecast,
        "forecast_confidence": confidence,
        "prediction_explanation": explanation,
    }
